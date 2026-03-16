# Notebook 03: Train a churn model with PySpark MLlib, log it to MLflow,
# and save it as an MLflow Spark model for MLServer.

import json
import os
from pathlib import Path

import mlflow
import mlflow.spark

from pyspark.ml import Pipeline
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator
from pyspark.ml.feature import VectorAssembler
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

os.environ.setdefault("JAVA_HOME", "/usr/lib/jvm/default-java")

PACKAGES = ",".join([
    "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2",
    "org.apache.iceberg:iceberg-aws-bundle:1.5.2",
    "software.amazon.awssdk:url-connection-client:2.25.53",
    "org.apache.hadoop:hadoop-aws:3.3.4",
    "com.amazonaws:aws-java-sdk-bundle:1.12.262",
    "org.postgresql:postgresql:42.7.3",
])

aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "mlplatform")
aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "MinioSecure123")
aws_region = os.environ.get("AWS_REGION", "us-east-1")
spark_master = os.environ.get("SPARK_MASTER", "spark://spark-master:7077")
s3_endpoint = os.environ.get("AWS_S3_ENDPOINT", "http://minio:9000")
iceberg_jdbc_uri = os.environ.get("ICEBERG_JDBC_URI", "jdbc:postgresql://postgres-iceberg:5432/iceberg_catalog")
iceberg_jdbc_user = os.environ.get("ICEBERG_JDBC_USER", "iceberg")
iceberg_jdbc_password = os.environ.get("ICEBERG_JDBC_PASSWORD", "iceberg123")

spark = (
    SparkSession.builder
    .appName("Lab-ChurnModel-PySparkMLlib")
    .master(spark_master)
    .config("spark.jars.packages", PACKAGES)
    .config("spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
    .config("spark.sql.catalog.warehouse", "org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.warehouse.type", "jdbc")
    .config("spark.sql.catalog.warehouse.uri", iceberg_jdbc_uri)
    .config("spark.sql.catalog.warehouse.jdbc.user", iceberg_jdbc_user)
    .config("spark.sql.catalog.warehouse.jdbc.password", iceberg_jdbc_password)
    .config("spark.sql.catalog.warehouse.jdbc.schema-version", "V1")
    .config("spark.sql.catalog.warehouse.warehouse", "s3://warehouse/")
    .config("spark.sql.catalog.warehouse.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
    .config("spark.sql.catalog.warehouse.http-client.type", "urlconnection")
    .config("spark.sql.catalog.warehouse.client.region", aws_region)
    .config("spark.sql.catalog.warehouse.s3.endpoint", s3_endpoint)
    .config("spark.sql.catalog.warehouse.s3.path-style-access", "true")
    .config("spark.sql.catalog.warehouse.s3.access-key-id", aws_access_key)
    .config("spark.sql.catalog.warehouse.s3.secret-access-key", aws_secret_key)
    .config("spark.hadoop.fs.s3a.endpoint", s3_endpoint)
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .config("spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
    .config("spark.hadoop.fs.s3a.access.key", aws_access_key)
    .config("spark.hadoop.fs.s3a.secret.key", aws_secret_key)
    .getOrCreate()
)

print(f"Spark session created: {spark.version}")

# ── Load training data from Iceberg ──────────────────────────────────────────
dataset = spark.sql("""
    SELECT *
    FROM warehouse.analytics.churn_training_dataset
    ORDER BY customer_id
""")
print(f"Training dataset: {dataset.count()} rows, {len(dataset.columns)} columns")
dataset.show(5)

# ── Cast feature columns and label ───────────────────────────────────────────
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

for fc in FEATURE_COLUMNS:
    dataset = dataset.withColumn(fc, col(fc).cast("double"))
dataset = dataset.withColumn("churn_label", col("churn_label").cast("double"))

churn_counts = dataset.groupBy("churn_label").count().collect()
print("Churn label distribution:")
for row in churn_counts:
    print(f"  label={int(row['churn_label'])}: {row['count']} rows")

# ── Build PySpark MLlib Pipeline ──────────────────────────────────────────────
train_df, test_df = dataset.randomSplit([0.7, 0.3], seed=42)
print(f"Train: {train_df.count()} rows | Test: {test_df.count()} rows")

assembler = VectorAssembler(inputCols=FEATURE_COLUMNS, outputCol="features")
rf = RandomForestClassifier(
    featuresCol="features",
    labelCol="churn_label",
    numTrees=50,
    seed=42,
)
pipeline = Pipeline(stages=[assembler, rf])

print("Fitting pipeline...")
model = pipeline.fit(train_df)

# ── Evaluate ──────────────────────────────────────────────────────────────────
predictions = model.transform(test_df)

acc_evaluator = MulticlassClassificationEvaluator(
    labelCol="churn_label", predictionCol="prediction", metricName="accuracy"
)
auc_evaluator = BinaryClassificationEvaluator(
    labelCol="churn_label", rawPredictionCol="rawPrediction", metricName="areaUnderROC"
)
accuracy = float(acc_evaluator.evaluate(predictions))
auc = float(auc_evaluator.evaluate(predictions))
print(f"Accuracy: {accuracy:.4f}")
print(f"AUC:      {auc:.4f}")

# ── Log to MLflow ─────────────────────────────────────────────────────────────
mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000"))
mlflow.set_experiment(os.environ.get("MLFLOW_EXPERIMENT_NAME", "retail-churn-demo"))

with mlflow.start_run(run_name="notebook-pyspark-random-forest"):
    mlflow.log_params({
        "model_type": "PySpark_RandomForestClassifier",
        "num_trees": 50,
        "framework": "pyspark.ml",
        "test_size": 0.3,
    })
    mlflow.log_metrics({"accuracy": accuracy, "auc": auc})
    mlflow.spark.log_model(model, artifact_path="spark-model")
    mlflow.set_tags({
        "lab": "notebook-03",
        "dataset": "churn_training_dataset",
    })
    print("Run logged to MLflow.")

# ── Save MLflow model for MLServer ────────────────────────────────────────────
model_dir = Path("/srv/jupyterhub/notebooks/churn-model")
mlflow_model_dir = model_dir / "mlflow_model"
mlflow_model_dir.mkdir(parents=True, exist_ok=True)

mlflow.spark.save_model(model, str(mlflow_model_dir))

model_settings = {
    "name": "churn-model",
    "implementation": "mlserver_mlflow.MLflowRuntime",
    "parameters": {"uri": "./mlflow_model", "version": "v1"},
}
(model_dir / "model-settings.json").write_text(
    json.dumps(model_settings, indent=2),
    encoding="utf-8",
)
print(f"MLflow Spark model saved to {mlflow_model_dir}")
print(f"model-settings.json written to {model_dir / 'model-settings.json'}")

# ── Save scored dataset for Evidently ────────────────────────────────────────
all_predictions = model.transform(dataset)
scored_pd = all_predictions.select(
    *FEATURE_COLUMNS,
    "churn_label",
    "prediction",
    "probability",
).toPandas()
scored_pd["prediction_probability"] = scored_pd["probability"].apply(lambda v: float(v[1]))
scored_pd = scored_pd.drop(columns=["probability"])
scored_pd.to_csv("/srv/jupyterhub/notebooks/scored_dataset.csv", index=False)
print(f"Scored dataset saved ({len(scored_pd)} rows)")

spark.stop()
print("Spark session stopped.")
