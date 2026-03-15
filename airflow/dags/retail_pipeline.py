"""
retail_pipeline.py

Daily orchestration for the teaching stack:
  1. Ingest source tables from demo-postgres into Iceberg
  2. Run dbt models and tests through Trino
  3. Publish feature parquet files for Feast and materialize them
  4. Validate marts with Great Expectations
  5. Train and log a model, then generate monitoring artifacts
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

with DAG(
    dag_id="retail_ml_pipeline",
    default_args=default_args,
    description="Ingest → transform → validate → feature store → training",
    start_date=datetime(2024, 1, 1),
    schedule="0 2 * * *",
    catchup=False,
    tags=["ml", "retail", "teaching"],
) as dag:
    ingest = BashOperator(
        task_id="ingest_raw",
        bash_command=f"{BOOTSTRAP} --step ingest_raw",
        doc_md="Loads source tables from demo Postgres into Iceberg.",
    )

    dbt_run = BashOperator(
        task_id="dbt_run_and_test",
        bash_command=(
            "dbt deps --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && "
            "dbt run --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && "
            "dbt test --project-dir /opt/dbt/retail --profiles-dir /opt/dbt"
        ),
        doc_md="Builds analytics marts through Trino.",
    )

    post_dbt = BashOperator(
        task_id="publish_features_and_train",
        bash_command=f"{BOOTSTRAP} --step post_dbt",
        doc_md="Publishes Feast parquet sources and trains the demo churn model.",
    )

    docs_refresh = BashOperator(
        task_id="refresh_docs_index",
        bash_command="test -f /opt/platform/bootstrap/seed_manifest.json",
        doc_md="Confirms that the teaching artifacts were regenerated.",
    )

    ingest >> dbt_run >> post_dbt >> docs_refresh
