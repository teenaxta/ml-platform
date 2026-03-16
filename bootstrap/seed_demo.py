from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import mlflow
import pandas as pd
import pyarrow as pa
import pyarrow.fs as pa_fs
import pyarrow.parquet as pq
import trino
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split


ROOT_DIR = Path(os.environ.get("ROOT_DIR", Path(__file__).resolve().parents[1]))
DBT_ROOT = ROOT_DIR / "dbt"
DBT_PROJECT = DBT_ROOT / "retail"
MLSERVER_MODEL_DIR = ROOT_DIR / "mlserver" / "models" / "churn-model"
TRINO_HOST = os.environ.get("TRINO_HOST", "trino")
TRINO_PORT = int(os.environ.get("TRINO_PORT", "8080"))
TRINO_ICEBERG_CATALOG = "iceberg"
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://minio:9000")
ICEBERG_JDBC_URI = os.environ.get(
    "ICEBERG_JDBC_URI",
    "jdbc:postgresql://postgres-iceberg:5432/iceberg_catalog",
)
ICEBERG_JDBC_USER = os.environ.get("ICEBERG_JDBC_USER", "iceberg")
ICEBERG_JDBC_PASSWORD = os.environ.get("ICEBERG_JDBC_PASSWORD", "iceberg123")


def log(message: str) -> None:
    print(f"[bootstrap] {message}", flush=True)


def wait_for_http(url: str, attempts: int = 40, delay: int = 5) -> None:
    import requests

    for _ in range(attempts):
      try:
          response = requests.get(url, timeout=5)
          if response.status_code < 500:
              return
      except Exception:
          pass
      time.sleep(delay)
    raise RuntimeError(f"Timed out waiting for {url}")


def wait_for_file(path: Path, attempts: int = 20, delay: int = 2) -> None:
    for _ in range(attempts):
        if path.exists():
            return
        time.sleep(delay)
    raise RuntimeError(f"Timed out waiting for {path}")


def trino_connection() -> trino.dbapi.Connection:
    return trino.dbapi.connect(
        host=TRINO_HOST,
        port=TRINO_PORT,
        user="trino",
        catalog="iceberg",
        schema="analytics",
    )


def trino_query(sql: str) -> pd.DataFrame:
    conn = trino_connection()
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    columns = [col[0] for col in cur.description]
    return pd.DataFrame(rows, columns=columns)


def trino_execute(sql: str) -> None:
    conn = trino_connection()
    cur = conn.cursor()
    cur.execute(sql)


def s3_filesystem() -> pa_fs.S3FileSystem:
    parsed = urlparse(S3_ENDPOINT)
    return pa_fs.S3FileSystem(
        access_key=os.environ["AWS_ACCESS_KEY_ID"],
        secret_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region=AWS_REGION,
        scheme=parsed.scheme or "http",
        endpoint_override=parsed.netloc or parsed.path,
    )


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3":
        raise ValueError(f"Expected s3:// URI, got {uri}")
    return parsed.netloc, parsed.path.lstrip("/").rstrip("/")


def write_parquet_to_s3(df: pd.DataFrame, uri: str) -> None:
    bucket, prefix = parse_s3_uri(uri)
    dataset_path = f"{bucket}/{prefix}"
    fs = s3_filesystem()
    fs.delete_dir_contents(dataset_path, missing_dir_ok=True)
    fs.create_dir(dataset_path, recursive=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    with fs.open_output_stream(f"{dataset_path}/part-00000.parquet") as sink:
        pq.write_table(table, sink)


def wait_for_trino_schema(schema: str, attempts: int = 24, delay: int = 5) -> None:
    for _ in range(attempts):
        try:
            schemas = trino_query("SELECT schema_name FROM iceberg.information_schema.schemata")
            if schema in schemas["schema_name"].tolist():
                return
        except Exception:
            pass
        time.sleep(delay)
    raise RuntimeError(f"Timed out waiting for Trino schema {schema}")


def ensure_seed_dirs() -> None:
    for path in [MLSERVER_MODEL_DIR, DBT_PROJECT / "target", ROOT_DIR / "evidently"]:
        path.mkdir(parents=True, exist_ok=True)


def ingest_raw() -> None:
    wait_for_http("http://trino:8080/v1/info", attempts=24, delay=5)
    trino_execute(f"CREATE SCHEMA IF NOT EXISTS {TRINO_ICEBERG_CATALOG}.retail_raw")
    trino_execute(f"CREATE SCHEMA IF NOT EXISTS {TRINO_ICEBERG_CATALOG}.analytics")
    source_queries = {
        "events": """
            SELECT
              event_id,
              customer_id,
              event_type,
              event_ts,
              json_format(metadata) AS metadata
            FROM postgresql.public.events
        """
    }
    tables = [
        "customers",
        "products",
        "orders",
        "order_items",
        "events",
        "payments",
        "shipments",
        "support_tickets",
    ]
    for table in tables:
        trino_execute(f"DROP TABLE IF EXISTS {TRINO_ICEBERG_CATALOG}.retail_raw.{table}")
        source_query = source_queries.get(table, f"SELECT * FROM postgresql.public.{table}")
        trino_execute(
            f"""
            CREATE TABLE {TRINO_ICEBERG_CATALOG}.retail_raw.{table} AS
            {source_query}
            """
        )
        row_count = int(
            trino_query(
                f"SELECT COUNT(*) AS row_count FROM {TRINO_ICEBERG_CATALOG}.retail_raw.{table}"
            )["row_count"].iloc[0]
        )
        log(f"Loaded {table}: {row_count} rows")
    wait_for_trino_schema("retail_raw")
    wait_for_trino_schema("analytics")
    log("Verified retail_raw and analytics schemas are visible in Trino.")


def publish_feast_sources() -> None:
    customer_stats = trino_query(
        """
        SELECT
          customer_id,
          age,
          country,
          is_premium,
          total_orders,
          lifetime_value,
          days_since_last_order,
          avg_order_value,
          event_timestamp
        FROM iceberg.analytics.customer_360
        """
    )
    write_parquet_to_s3(customer_stats, "s3://warehouse/feast/customer_stats/")

    customer_behavior = trino_query(
        """
        SELECT
          customer_id,
          page_views_30d,
          add_to_cart_30d,
          support_tickets,
          checkout_rate,
          event_timestamp
        FROM iceberg.analytics.customer_behavior
        """
    )
    write_parquet_to_s3(customer_behavior, "s3://warehouse/feast/customer_behavior/")

    product_stats = trino_query(
        """
        SELECT
          product_id,
          category,
          unit_price,
          times_ordered,
          units_sold,
          revenue,
          stock_qty,
          event_timestamp
        FROM iceberg.analytics.product_performance
        """
    )
    write_parquet_to_s3(product_stats, "s3://warehouse/feast/product_stats/")


def train_and_log_model() -> pd.DataFrame:
    dataset = trino_query(
        """
        SELECT *
        FROM iceberg.analytics.churn_training_dataset
        ORDER BY customer_id
        """
    )
    feature_columns = [
        "age",
        "total_orders",
        "lifetime_value",
        "avg_order_value",
        "days_since_last_order",
        "page_views_30d",
        "support_tickets",
        "return_rate",
    ]
    X = dataset[feature_columns]
    y = dataset["churn_label"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )

    model = RandomForestClassifier(n_estimators=50, random_state=42)
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    accuracy = float(accuracy_score(y_test, predictions))
    f1 = float(f1_score(y_test, predictions))

    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    mlflow.set_experiment("retail-churn-demo")
    with mlflow.start_run(run_name="bootstrap-random-forest"):
        mlflow.log_params({"model_type": "RandomForestClassifier", "n_estimators": 50})
        mlflow.log_metrics({"accuracy": accuracy, "f1_score": f1})
        mlflow.set_tags({"demo_model_path": "mlserver/models/churn-model/model.joblib"})

    MLSERVER_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MLSERVER_MODEL_DIR / "model.joblib"
    with model_path.open("wb") as handle:
        import joblib

        joblib.dump(model, handle)

    model_settings = {
        "name": "churn-model",
        "implementation": "mlserver_sklearn.SKLearnModel",
        "parameters": {"uri": "./model.joblib", "version": "v1"},
    }
    (MLSERVER_MODEL_DIR / "model-settings.json").write_text(
        json.dumps(model_settings, indent=2),
        encoding="utf-8",
    )

    scored = dataset.copy()
    scored["prediction"] = model.predict(X)
    probabilities = model.predict_proba(X)
    if len(model.classes_) == 1:
        positive_class_probability = 1.0 if int(model.classes_[0]) == 1 else 0.0
        scored["prediction_probability"] = positive_class_probability
    else:
        positive_class_index = list(model.classes_).index(1)
        scored["prediction_probability"] = probabilities[:, positive_class_index]
    scored.to_csv(ROOT_DIR / "evidently" / "scored_dataset.csv", index=False)
    return scored


def write_seed_manifest() -> None:
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dbt_docs": "dbt/retail/target/index.html",
        "great_expectations_docs": "great_expectations/uncommitted/data_docs/local_site/index.html",
        "evidently_report": "evidently/reports/index.html",
        "mlserver_model": "mlserver/models/churn-model/model.joblib",
    }
    (ROOT_DIR / "bootstrap" / "seed_manifest.json").write_text(
        __import__("json").dumps(manifest, indent=2),
        encoding="utf-8",
    )


def run_post_dbt() -> None:
    ensure_seed_dirs()
    wait_for_http("http://trino:8080/v1/info")
    wait_for_http("http://mlflow:5000")
    publish_feast_sources()
    train_and_log_model()
    write_seed_manifest()
    log("Post-dbt bootstrap complete.")


def run_ingest() -> None:
    ensure_seed_dirs()
    ingest_raw()
    log("Raw ingest complete.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", choices=["ingest_raw", "post_dbt"], required=True)
    args = parser.parse_args()

    if args.step == "ingest_raw":
        run_ingest()
    elif args.step == "post_dbt":
        run_post_dbt()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
