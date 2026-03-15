# Walkthrough 01: Ingest from Postgres, then inspect the lakehouse

import os
from pyspark.sql import SparkSession


os.environ.setdefault("JAVA_HOME", "/usr/lib/jvm/default-java")

PACKAGES = ",".join(
    [
        "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2",
        "org.apache.iceberg:iceberg-aws-bundle:1.5.2",
        "software.amazon.awssdk:url-connection-client:2.25.53",
        "org.apache.hadoop:hadoop-aws:3.3.4",
        "com.amazonaws:aws-java-sdk-bundle:1.12.262",
        "org.postgresql:postgresql:42.7.3",
    ]
)


def get_spark() -> SparkSession:
    if not os.path.exists(os.environ["JAVA_HOME"]):
        raise RuntimeError(
            "JAVA_HOME points to a missing path. Rebuild the jupyterhub image so Java is installed."
        )

    aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "mlplatform")
    aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "MinioSecure123")
    aws_region = os.environ.get("AWS_REGION", "us-east-1")
    spark_master = os.environ.get("SPARK_MASTER", "spark://spark-master:7077")

    return (
        SparkSession.builder
        .appName("RetailIngestWalkthrough")
        .master(spark_master)
        .config("spark.jars.packages", PACKAGES)
        .config(
            "spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        )
        .config("spark.sql.catalog.warehouse", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.warehouse.type", "jdbc")
        .config(
            "spark.sql.catalog.warehouse.uri",
            os.environ.get(
                "ICEBERG_JDBC_URI",
                "jdbc:postgresql://postgres-iceberg:5432/iceberg_catalog",
            ),
        )
        .config("spark.sql.catalog.warehouse.jdbc.user", os.environ.get("ICEBERG_JDBC_USER", "iceberg"))
        .config(
            "spark.sql.catalog.warehouse.jdbc.password",
            os.environ.get("ICEBERG_JDBC_PASSWORD", "iceberg123"),
        )
        .config("spark.sql.catalog.warehouse.jdbc.schema-version", "V1")
        .config("spark.sql.catalog.warehouse.warehouse", "s3://warehouse/")
        .config("spark.sql.catalog.warehouse.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        .config("spark.sql.catalog.warehouse.http-client.type", "urlconnection")
        .config("spark.sql.catalog.warehouse.client.region", aws_region)
        .config("spark.sql.catalog.warehouse.s3.endpoint", os.environ.get("AWS_S3_ENDPOINT", "http://minio:9000"))
        .config("spark.sql.catalog.warehouse.s3.path-style-access", "true")
        .config("spark.sql.catalog.warehouse.s3.access-key-id", aws_access_key)
        .config("spark.sql.catalog.warehouse.s3.secret-access-key", aws_secret_key)
        .config("spark.hadoop.fs.s3a.endpoint", os.environ.get("AWS_S3_ENDPOINT", "http://minio:9000"))
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


spark = get_spark()

demo_postgres_host = os.environ.get("DEMO_POSTGRES_HOST", "demo-postgres")
demo_postgres_port = os.environ.get("DEMO_POSTGRES_PORT", "5432")
demo_postgres_db = os.environ.get("DEMO_POSTGRES_DB", "retail_db")

jdbc_url = f"jdbc:postgresql://{demo_postgres_host}:{demo_postgres_port}/{demo_postgres_db}"
jdbc_props = {
    "user": os.environ.get("DEMO_POSTGRES_USER", "analyst"),
    "password": os.environ.get("DEMO_POSTGRES_PASSWORD", "analyst123"),
    "driver": "org.postgresql.Driver",
}

raw_tables = [
    "customers",
    "products",
    "orders",
    "order_items",
    "events",
    "payments",
    "shipments",
    "support_tickets",
]

spark.sql("CREATE NAMESPACE IF NOT EXISTS warehouse.retail_raw")

for table in raw_tables:
    df = spark.read.jdbc(jdbc_url, f"public.{table}", properties=jdbc_props)
    df.writeTo(f"warehouse.retail_raw.{table}").createOrReplace()
    print(f"{table}: {df.count()} rows")

spark.sql("SHOW TABLES IN warehouse.retail_raw").show(truncate=False)
spark.sql("SELECT * FROM warehouse.retail_raw.orders LIMIT 5").show()
