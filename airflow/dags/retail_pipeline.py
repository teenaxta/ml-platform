"""
retail_pipeline.py  —  end-to-end ML pipeline DAG

Schedule: daily at 02:00
Steps:
  1. ingest_postgres   — pulls data from demo-postgres into Iceberg via Spark
  2. dbt_run           — runs dbt models to produce clean feature tables
  3. dbt_test          — validates dbt models
  4. feast_materialize — materialises features from offline → online store

To trigger manually: Airflow UI → retail_ml_pipeline → ▶ Trigger DAG
"""

from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "ml-platform",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="retail_ml_pipeline",
    default_args=default_args,
    description="Ingest → dbt transform → feature materialisation",
    start_date=datetime(2024, 1, 1),
    schedule="0 2 * * *",   # 02:00 every day
    catchup=False,
    tags=["ml", "retail"],
) as dag:

    # ── Step 1: Ingest from Postgres into Iceberg ─────────────
    # Runs the ingest notebook as a script inside JupyterHub's container.
    # Alternatively, call Airbyte's API here for automated CDC sync.
    ingest = BashOperator(
        task_id="ingest_postgres",
        bash_command="""
            docker exec jupyterhub python3 -c "
from pyspark.sql import SparkSession
import os

spark = SparkSession.builder \\
    .appName('DailyIngest') \\
    .config('spark.hadoop.fs.s3a.access.key', os.environ['AWS_ACCESS_KEY_ID']) \\
    .config('spark.hadoop.fs.s3a.secret.key', os.environ['AWS_SECRET_ACCESS_KEY']) \\
    .getOrCreate()

jdbc = 'jdbc:postgresql://demo-postgres:5432/retail_db'
props = {'user': 'analyst', 'password': 'analyst123', 'driver': 'org.postgresql.Driver'}

spark.sql('CREATE NAMESPACE IF NOT EXISTS warehouse.retail')
for table in ['customers', 'orders', 'order_items', 'events', 'products']:
    df = spark.read.jdbc(jdbc, f'public.{table}', properties=props)
    df.writeTo(f'warehouse.retail.{table}').createOrReplace()
    print(f'Loaded {table}: {df.count()} rows')
"
        """,
        doc_md="Pulls all retail tables from demo-postgres into Iceberg on MinIO.",
    )

    # ── Step 2: Run dbt models ─────────────────────────────────
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="docker exec dbt bash -c 'cd /opt/dbt/retail && dbt run --profiles-dir /opt/dbt'",
        doc_md="Transforms raw Iceberg tables into clean feature models.",
    )

    # ── Step 3: Test dbt models ────────────────────────────────
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="docker exec dbt bash -c 'cd /opt/dbt/retail && dbt test --profiles-dir /opt/dbt'",
        doc_md="Runs dbt data quality tests. Fails the pipeline if tests fail.",
    )

    # ── Step 4: Materialise features into Feast online store ───
    feast_materialize = BashOperator(
        task_id="feast_materialize",
        bash_command="""
            docker exec feast feast -c /opt/feast/project materialize-incremental \
                $(date -u +%Y-%m-%dT%H:%M:%S)
        """,
        doc_md="Pushes latest feature values from offline (MinIO) to online (SQLite) store.",
    )

    # ── Pipeline order ─────────────────────────────────────────
    ingest >> dbt_run >> dbt_test >> feast_materialize
