"""
retail_pipeline.py

Daily orchestration for the teaching stack.

Data flow:
  Airbyte (external, via abctl) syncs demo-postgres → Iceberg retail_raw
      ↓
  1. verify_airbyte_sync  — confirm all 8 raw tables exist in Trino
  2. dbt_run_and_test     — build analytics marts through Trino
  3. publish_features_and_train — Spark feature engineering + PySpark MLlib training
  4. refresh_docs_index   — confirm teaching artifacts were generated

Note: Airbyte runs outside this DAG in its own Kubernetes cluster (abctl).
Trigger an Airbyte sync manually from http://localhost:8000 before running
this DAG, or configure an Airbyte schedule to run before 2 AM.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    "owner": "ml-platform",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

BOOTSTRAP = "python /opt/bootstrap/seed_demo.py"

# Verify all 8 retail_raw tables are present in Trino (written by Airbyte).
# This acts as the gate: if Airbyte hasn't synced yet, this task fails fast.
VERIFY_RAW_TABLES_CMD = """
python3 -c "
import trino, sys
conn = trino.dbapi.connect(host='trino', port=8080, user='trino', catalog='iceberg', schema='retail_raw')
cur = conn.cursor()
cur.execute('SHOW TABLES FROM iceberg.retail_raw')
tables = {row[0] for row in cur.fetchall()}
expected = {'customers','products','orders','order_items','events','payments','shipments','support_tickets'}
missing = expected - tables
if missing:
    print(f'[verify_airbyte_sync] MISSING tables: {missing}', flush=True)
    print('Run an Airbyte sync from http://localhost:8000 first.', flush=True)
    sys.exit(1)
print(f'[verify_airbyte_sync] All 8 raw tables present: {sorted(tables)}', flush=True)
"
"""

with DAG(
    dag_id="retail_ml_pipeline",
    default_args=default_args,
    description="Airbyte ingest → dbt transform → Spark feature eng + PySpark MLlib train → serve",
    start_date=datetime(2024, 1, 1),
    schedule="0 2 * * *",
    catchup=False,
    tags=["ml", "retail", "teaching"],
) as dag:
    verify_sync = BashOperator(
        task_id="verify_airbyte_sync",
        bash_command=VERIFY_RAW_TABLES_CMD,
        doc_md=(
            "Confirms Airbyte has synced all 8 source tables into iceberg.retail_raw. "
            "Airbyte runs externally via abctl — trigger a sync from http://localhost:8000 "
            "before this DAG runs, or configure an Airbyte schedule."
        ),
    )

    dbt_run = BashOperator(
        task_id="dbt_run_and_test",
        bash_command=(
            "dbt deps --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && "
            "dbt run --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && "
            "dbt test --project-dir /opt/dbt/retail --profiles-dir /opt/dbt"
        ),
        doc_md="Builds staging and analytics mart models through Trino into Iceberg.",
    )

    post_dbt = BashOperator(
        task_id="publish_features_and_train",
        bash_command=f"{BOOTSTRAP} --step post_dbt",
        doc_md=(
            "Uses PySpark to read Iceberg marts, write Feast parquet sources to MinIO, "
            "and train a PySpark MLlib RandomForest churn model logged to MLflow."
        ),
    )

    docs_refresh = BashOperator(
        task_id="refresh_docs_index",
        bash_command="test -f /opt/platform/bootstrap/seed_manifest.json",
        doc_md="Confirms that the teaching artifacts (model, Feast sources) were regenerated.",
    )

    verify_sync >> dbt_run >> post_dbt >> docs_refresh
