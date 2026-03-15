from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import pandas as pd
import trino
from pyspark.sql import SparkSession
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split


ROOT_DIR = Path(os.environ.get("ROOT_DIR", Path(__file__).resolve().parents[1]))
DBT_ROOT = ROOT_DIR / "dbt"
DBT_PROJECT = DBT_ROOT / "retail"
MLSERVER_MODEL_DIR = ROOT_DIR / "mlserver" / "models" / "churn-model"
SPARK_MASTER_URL = os.environ.get("SPARK_MASTER_URL", "spark://spark-master:7077")
TRINO_HOST = os.environ.get("TRINO_HOST", "trino")
TRINO_PORT = int(os.environ.get("TRINO_PORT", "8080"))
WAREHOUSE_CATALOG = "warehouse"
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
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


def get_spark() -> SparkSession:
    packages = ",".join(
        [
            "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2",
            "org.apache.iceberg:iceberg-aws-bundle:1.5.2",
            "software.amazon.awssdk:url-connection-client:2.25.53",
            "org.apache.hadoop:hadoop-aws:3.3.4",
            "com.amazonaws:aws-java-sdk-bundle:1.12.262",
            "org.postgresql:postgresql:42.7.3",
        ]
    )
    builder = (
        SparkSession.builder.appName("ml-platform-bootstrap")
        .master(SPARK_MASTER_URL)
        .config("spark.jars.packages", packages)
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config("spark.sql.catalog.warehouse", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.warehouse.type", "jdbc")
        .config("spark.sql.catalog.warehouse.uri", ICEBERG_JDBC_URI)
        .config("spark.sql.catalog.warehouse.jdbc.user", ICEBERG_JDBC_USER)
        .config("spark.sql.catalog.warehouse.jdbc.password", ICEBERG_JDBC_PASSWORD)
        .config("spark.sql.catalog.warehouse.jdbc.schema-version", "V1")
        .config("spark.sql.catalog.warehouse.warehouse", "s3://warehouse/")
        .config("spark.sql.catalog.warehouse.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .config("spark.sql.catalog.warehouse.http-client.type", "urlconnection")
        .config("spark.sql.catalog.warehouse.client.region", AWS_REGION)
        .config("spark.sql.catalog.warehouse.s3.endpoint", "http://minio:9000")
        .config("spark.sql.catalog.warehouse.s3.path-style-access", "true")
        .config("spark.sql.catalog.warehouse.s3.access-key-id", os.environ["AWS_ACCESS_KEY_ID"])
        .config(
            "spark.sql.catalog.warehouse.s3.secret-access-key",
            os.environ["AWS_SECRET_ACCESS_KEY"],
        )
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.access.key", os.environ["AWS_ACCESS_KEY_ID"])
        .config("spark.hadoop.fs.s3a.secret.key", os.environ["AWS_SECRET_ACCESS_KEY"])
        .config("spark.executorEnv.AWS_ACCESS_KEY_ID", os.environ["AWS_ACCESS_KEY_ID"])
        .config("spark.executorEnv.AWS_SECRET_ACCESS_KEY", os.environ["AWS_SECRET_ACCESS_KEY"])
        .config("spark.executorEnv.AWS_REGION", AWS_REGION)
        .config("spark.executorEnv.AWS_DEFAULT_REGION", AWS_REGION)
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    )
    return builder.getOrCreate()


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
    spark = get_spark()
    spark.sql("CREATE NAMESPACE IF NOT EXISTS warehouse.retail_raw")
    spark.sql("CREATE NAMESPACE IF NOT EXISTS warehouse.analytics")
    jdbc_url = "jdbc:postgresql://demo-postgres:5432/retail_db"
    props = {"user": "analyst", "password": "analyst123", "driver": "org.postgresql.Driver"}
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
        df = spark.read.jdbc(jdbc_url, f"public.{table}", properties=props)
        df.writeTo(f"{WAREHOUSE_CATALOG}.retail_raw.{table}").createOrReplace()
        log(f"Loaded {table}: {df.count()} rows")
    spark.stop()
    wait_for_http("http://trino:8080/v1/info", attempts=24, delay=5)
    wait_for_trino_schema("retail_raw")
    wait_for_trino_schema("analytics")
    log("Verified retail_raw and analytics schemas are visible in Trino.")


def publish_feast_sources() -> None:
    spark = get_spark()
    customer_stats = spark.sql(
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
        FROM warehouse.analytics.customer_360
        """
    )
    customer_stats.write.mode("overwrite").parquet("s3a://warehouse/feast/customer_stats/")

    customer_behavior = spark.sql(
        """
        SELECT
          customer_id,
          page_views_30d,
          add_to_cart_30d,
          support_tickets,
          checkout_rate,
          event_timestamp
        FROM warehouse.analytics.customer_behavior
        """
    )
    customer_behavior.write.mode("overwrite").parquet("s3a://warehouse/feast/customer_behavior/")

    product_stats = spark.sql(
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
        FROM warehouse.analytics.product_performance
        """
    )
    product_stats.write.mode("overwrite").parquet("s3a://warehouse/feast/product_stats/")
    spark.stop()


def train_and_log_model() -> pd.DataFrame:
    spark = get_spark()
    dataset = spark.sql(
        """
        SELECT *
        FROM warehouse.analytics.churn_training_dataset
        ORDER BY customer_id
        """
    ).toPandas()
    spark.stop()
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
