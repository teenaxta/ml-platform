from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(os.environ.get("ROOT_DIR", Path(__file__).resolve().parents[1]))
DBT_ROOT = ROOT_DIR / "dbt"
DBT_PROJECT = DBT_ROOT / "retail"
TRINO_HOST = os.environ.get("TRINO_HOST", "trino")
TRINO_PORT = int(os.environ.get("TRINO_PORT", "8080"))
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_ENDPOINT = os.environ.get("MLFLOW_S3_ENDPOINT_URL", os.environ.get("S3_ENDPOINT", "http://minio:9000"))
SPARK_MASTER_URL = os.environ.get("SPARK_MASTER_URL", "spark://spark-master:7077")
ICEBERG_JDBC_URI = os.environ.get(
    "ICEBERG_JDBC_URI",
    "jdbc:postgresql://postgres-iceberg:5432/iceberg_catalog",
)
ICEBERG_JDBC_USER = os.environ.get("ICEBERG_JDBC_USER", "iceberg")
ICEBERG_JDBC_PASSWORD = os.environ.get("ICEBERG_JDBC_PASSWORD", "iceberg123")


FEATURE_COLUMNS = [
    "age",
    "total_orders",
    "lifetime_value",
    "avg_order_value",
    "days_since_last_order",
    "page_views_30d",
    "support_tickets",
    "return_rate",
]


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


def get_spark():
    """Create a SparkSession configured for Iceberg + MinIO."""
    from pyspark.sql import SparkSession

    aws_access_key = os.environ["AWS_ACCESS_KEY_ID"]
    aws_secret_key = os.environ["AWS_SECRET_ACCESS_KEY"]

    PACKAGES = ",".join([
        "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2",
        "org.apache.iceberg:iceberg-aws-bundle:1.5.2",
        "software.amazon.awssdk:url-connection-client:2.25.53",
        "org.apache.hadoop:hadoop-aws:3.3.4",
        "com.amazonaws:aws-java-sdk-bundle:1.12.262",
        "org.postgresql:postgresql:42.7.3",
    ])

    return (
        SparkSession.builder
        .appName("RetailPlatformBootstrap")
        .master(SPARK_MASTER_URL)
        .config("spark.jars.packages", PACKAGES)
        # Memory tuning for Docker environments
        .config("spark.driver.memory", "1g")
        .config("spark.executor.memory", "1g")
        .config("spark.executor.memoryOverhead", "512m")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.default.parallelism", "2")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.network.timeout", "300s")
        .config("spark.executor.heartbeatInterval", "60s")
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
        .config("spark.sql.catalog.warehouse.s3.endpoint", S3_ENDPOINT)
        .config("spark.sql.catalog.warehouse.s3.path-style-access", "true")
        .config("spark.sql.catalog.warehouse.s3.access-key-id", aws_access_key)
        .config("spark.sql.catalog.warehouse.s3.secret-access-key", aws_secret_key)
        .config("spark.hadoop.fs.s3a.endpoint", S3_ENDPOINT)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config(
            "spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider",
        )
        .config("spark.hadoop.fs.s3a.access.key", aws_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", aws_secret_key)
        .getOrCreate()
    )


def publish_feast_sources(spark) -> None:
    """Read analytics marts from Iceberg via Spark and write Parquet to MinIO for Feast."""
    log("Publishing Feast feature sources via Spark...")

    customer_stats = spark.sql("""
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
    """)
    customer_stats.write.mode("overwrite").parquet("s3a://warehouse/feast/customer_stats/")
    log(f"  customer_stats: {customer_stats.count()} rows")

    customer_behavior = spark.sql("""
        SELECT
          customer_id,
          page_views_30d,
          add_to_cart_30d,
          support_tickets,
          checkout_rate,
          event_timestamp
        FROM warehouse.analytics.customer_behavior
    """)
    customer_behavior.write.mode("overwrite").parquet("s3a://warehouse/feast/customer_behavior/")
    log(f"  customer_behavior: {customer_behavior.count()} rows")

    product_stats = spark.sql("""
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
    """)
    product_stats.write.mode("overwrite").parquet("s3a://warehouse/feast/product_stats/")
    log(f"  product_stats: {product_stats.count()} rows")

    log("Feast feature sources published.")


def train_and_log_model(spark) -> None:
    """Train a churn model with PySpark MLlib and log to MLflow."""
    import mlflow
    import mlflow.spark

    from pyspark.ml import Pipeline
    from pyspark.ml.classification import RandomForestClassifier
    from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator
    from pyspark.ml.feature import VectorAssembler
    from pyspark.sql.functions import col

    log("Loading churn training dataset from Iceberg...")
    dataset = spark.sql("""
        SELECT *
        FROM warehouse.analytics.churn_training_dataset
        ORDER BY customer_id
    """)

    for feature_col in FEATURE_COLUMNS:
        dataset = dataset.withColumn(feature_col, col(feature_col).cast("double"))
    dataset = dataset.withColumn("churn_label", col("churn_label").cast("double"))

    dataset = dataset.cache()
    row_count = dataset.count()
    train_df, test_df = dataset.randomSplit([0.7, 0.3], seed=42)
    log(f"  Dataset: {row_count} rows | Train: {train_df.count()}, Test: {test_df.count()}")

    assembler = VectorAssembler(inputCols=FEATURE_COLUMNS, outputCol="features")
    rf = RandomForestClassifier(
        featuresCol="features",
        labelCol="churn_label",
        numTrees=20,
        maxDepth=5,
        seed=42,
    )
    pipeline = Pipeline(stages=[assembler, rf])

    log("Training PySpark MLlib RandomForestClassifier pipeline...")
    model = pipeline.fit(train_df)

    predictions = model.transform(test_df)

    acc_evaluator = MulticlassClassificationEvaluator(
        labelCol="churn_label", predictionCol="prediction", metricName="accuracy"
    )
    auc_evaluator = BinaryClassificationEvaluator(
        labelCol="churn_label", rawPredictionCol="rawPrediction", metricName="areaUnderROC"
    )
    accuracy = float(acc_evaluator.evaluate(predictions))
    auc = float(auc_evaluator.evaluate(predictions))
    log(f"  Accuracy: {accuracy:.4f}, AUC: {auc:.4f}")

    all_predictions = model.transform(dataset)
    scored_pd = all_predictions.select(
        *FEATURE_COLUMNS,
        "churn_label",
        "prediction",
        "probability",
    ).toPandas()

    scored_pd["prediction_probability"] = scored_pd["probability"].apply(lambda v: float(v[1]))
    scored_pd = scored_pd.drop(columns=["probability"])
    scored_pd.to_csv(ROOT_DIR / "evidently" / "scored_dataset.csv", index=False)
    log("  Scored dataset written for Evidently.")

    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    mlflow.set_experiment("retail-churn-demo")

    with mlflow.start_run(run_name="bootstrap-pyspark-random-forest"):
        mlflow.log_params({
            "model_type": "PySpark_RandomForestClassifier",
            "num_trees": 50,
            "framework": "pyspark.ml",
        })
        mlflow.log_metrics({"accuracy": accuracy, "auc": auc})
        mlflow.set_tags({"training_framework": "PySpark MLlib"})
        mlflow.spark.log_model(model, artifact_path="spark-model")
        log("  Model logged to MLflow.")


def write_seed_manifest() -> None:
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dbt_docs": "dbt/retail/target/index.html",
        "great_expectations_docs": "great_expectations/uncommitted/data_docs/local_site/index.html",
        "evidently_report": "evidently/reports/index.html",
    }
    (ROOT_DIR / "bootstrap" / "seed_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )


def ensure_seed_dirs() -> None:
    for path in [DBT_PROJECT / "target", ROOT_DIR / "evidently"]:
        path.mkdir(parents=True, exist_ok=True)


def run_post_dbt() -> None:
    ensure_seed_dirs()
    wait_for_http("http://trino:8080/v1/info")
    wait_for_http("http://mlflow:5000")

    log("Creating Spark session...")
    spark = get_spark()
    try:
        publish_feast_sources(spark)
        train_and_log_model(spark)
    finally:
        try:
            spark.stop()
        except Exception:
            pass
        log("Spark session stopped.")

    write_seed_manifest()
    log("Post-dbt bootstrap complete.")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--step",
        choices=["post_dbt"],
        required=True,
        help="post_dbt: publish Feast sources and train model (Airbyte handles raw ingestion)",
    )
    args = parser.parse_args()

    if args.step == "post_dbt":
        run_post_dbt()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
