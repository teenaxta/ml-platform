# JupyterHub Environment Configuration Guide

This guide explains how to use JupyterHub in the ML platform — login, environment setup, Spark configuration, package management, resource limits, and best practices.

---

## 1. Logging In

### First-time admin login

1. Open `http://localhost:8888` in your browser.
2. Enter username `admin` and the password from `JUPYTERHUB_ADMIN_PASSWORD` in your `.env` file.
3. JupyterHub will start a JupyterLab server for you. This takes 5–15 seconds.
4. You should see the JupyterLab interface with a file browser on the left and a launcher on the right.

### Creating additional users

JupyterHub is configured with open signup (`NativeAuthenticator`):

1. On the login page, click **"Sign up"**.
2. Choose a username and a password (minimum 8 characters).
3. The admin must authorize new users: go to `http://localhost:8888/hub/authorize` while logged in as admin.
4. Click **"Authorize"** next to the new user's name.
5. The user can now log in.

### What happens when you log in

JupyterHub spawns a JupyterLab server process inside the `jupyterhub` container. Each user gets their own server with:
- **4 GB memory limit** (configurable via `c.Spawner.mem_limit` in `jupyterhub_config.py`)
- **2 CPU cores limit** (configurable via `c.Spawner.cpu_limit`)
- Access to all environment variables listed in Section 2

---

## 2. Pre-configured Environment Variables

Every JupyterHub notebook session has these environment variables available automatically. They are set in `jupyterhub/jupyterhub_config.py` under `c.Spawner.environment`.

### Spark and compute

| Variable | Default Value | What it connects to |
|---|---|---|
| `SPARK_MASTER` | `spark://spark-master:7077` | Spark cluster master |
| `JAVA_HOME` | `/usr/lib/jvm/default-java` | JDK for PySpark |
| `PYSPARK_PYTHON` | `python3` | Python interpreter for Spark workers |
| `PYSPARK_DRIVER_PYTHON` | `python3` | Python interpreter for Spark driver |

### Trino (SQL query engine)

| Variable | Default Value | What it connects to |
|---|---|---|
| `TRINO_HOST` | `trino` | Trino coordinator |
| `TRINO_PORT` | `8080` | Trino HTTP port |
| `TRINO_USER` | `trino` | Trino user |
| `TRINO_CATALOG` | `iceberg` | Default catalog |
| `TRINO_SCHEMA` | `analytics` | Default schema |

### MLflow

| Variable | Default Value | What it connects to |
|---|---|---|
| `MLFLOW_TRACKING_URI` | `http://mlflow:5000` | MLflow tracking server |
| `MLFLOW_TRACKING_USERNAME` | from `.env` | MLflow auth |
| `MLFLOW_TRACKING_PASSWORD` | from `.env` | MLflow auth |

### MinIO / S3

| Variable | Default Value | What it connects to |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | from `.env` | MinIO credentials |
| `AWS_SECRET_ACCESS_KEY` | from `.env` | MinIO credentials |
| `AWS_S3_ENDPOINT` | `http://minio:9000` | MinIO S3 endpoint |
| `AWS_REGION` | `us-east-1` | Required by S3 clients |

### Demo PostgreSQL

| Variable | Default Value | What it connects to |
|---|---|---|
| `DEMO_POSTGRES_HOST` | `demo-postgres` | Source database host |
| `DEMO_POSTGRES_PORT` | `5432` | Source database port |
| `DEMO_POSTGRES_DB` | `retail_db` | Source database name |
| `DEMO_POSTGRES_USER` | `analyst` | Source database user |
| `DEMO_POSTGRES_PASSWORD` | `analyst123` | Source database password |

### Iceberg catalog

| Variable | Default Value | What it connects to |
|---|---|---|
| `ICEBERG_JDBC_URI` | `jdbc:postgresql://postgres-iceberg:5432/iceberg_catalog` | Iceberg catalog backend |
| `ICEBERG_JDBC_USER` | `iceberg` | Catalog user |
| `ICEBERG_JDBC_PASSWORD` | `iceberg123` | Catalog password |

### How to use these in a notebook

```python
import os

# Example: connect to Trino using environment variables
trino_host = os.environ.get("TRINO_HOST", "trino")
trino_port = int(os.environ.get("TRINO_PORT", "8080"))
print(f"Trino: {trino_host}:{trino_port}")

# Example: connect to MinIO
s3_endpoint = os.environ.get("AWS_S3_ENDPOINT", "http://minio:9000")
print(f"MinIO: {s3_endpoint}")
```

---

## 3. Spark Configuration

### How Spark fits into the platform

Spark is used for two workloads in this platform:

1. **Feature engineering** — reading Iceberg analytics marts, computing complex features (joins, window functions, log-transforms, normalization), and writing Parquet files to MinIO for Feast. This is work that SQL/dbt could not do efficiently at scale.

2. **ML model training** — training the churn model using `pyspark.ml.Pipeline` with `VectorAssembler` and `RandomForestClassifier`. This is the production-grade approach: the model trains where the data lives, distributing both data loading and computation across the Spark cluster.

Spark is **not** used for raw data ingestion — that is handled by Airbyte.

### How Spark is set up

The JupyterHub container has PySpark 3.5.1 installed. Spark configuration is provided via a mounted config file:

- **File in the repo**: `spark/conf/spark-defaults.conf`
- **Mounted to**: `/usr/local/spark/conf/spark-defaults.conf` inside the JupyterHub container

This config file pre-configures:
- Iceberg Spark extensions and catalog
- S3/MinIO filesystem access
- Performance settings (adaptive query execution, Kryo serializer)

### Creating a Spark session in a notebook

```python
import os
from pyspark.sql import SparkSession

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

spark = (
    SparkSession.builder
    .appName("MyNotebookJob")
    .master(os.environ.get("SPARK_MASTER", "spark://spark-master:7077"))
    .config("spark.jars.packages", PACKAGES)
    .config("spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
    .config("spark.sql.catalog.warehouse", "org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.warehouse.type", "jdbc")
    .config("spark.sql.catalog.warehouse.uri",
            os.environ.get("ICEBERG_JDBC_URI",
                           "jdbc:postgresql://postgres-iceberg:5432/iceberg_catalog"))
    .config("spark.sql.catalog.warehouse.jdbc.user",
            os.environ.get("ICEBERG_JDBC_USER", "iceberg"))
    .config("spark.sql.catalog.warehouse.jdbc.password",
            os.environ.get("ICEBERG_JDBC_PASSWORD", "iceberg123"))
    .config("spark.sql.catalog.warehouse.jdbc.schema-version", "V1")
    .config("spark.sql.catalog.warehouse.warehouse", "s3://warehouse/")
    .config("spark.sql.catalog.warehouse.io-impl",
            "org.apache.iceberg.aws.s3.S3FileIO")
    .config("spark.sql.catalog.warehouse.http-client.type", "urlconnection")
    .config("spark.sql.catalog.warehouse.client.region",
            os.environ.get("AWS_REGION", "us-east-1"))
    .config("spark.sql.catalog.warehouse.s3.endpoint",
            os.environ.get("AWS_S3_ENDPOINT", "http://minio:9000"))
    .config("spark.sql.catalog.warehouse.s3.path-style-access", "true")
    .config("spark.sql.catalog.warehouse.s3.access-key-id", aws_access_key)
    .config("spark.sql.catalog.warehouse.s3.secret-access-key", aws_secret_key)
    .config("spark.hadoop.fs.s3a.endpoint",
            os.environ.get("AWS_S3_ENDPOINT", "http://minio:9000"))
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.impl",
            "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .config("spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
    .config("spark.hadoop.fs.s3a.access.key", aws_access_key)
    .config("spark.hadoop.fs.s3a.secret.key", aws_secret_key)
    .getOrCreate()
)
```

### Verifying that Spark is connected

After creating the session, run:

```python
spark.sql("SHOW NAMESPACES IN warehouse").show()
```

You should see `retail_raw` and `analytics` listed (if bootstrap has run).

### Monitoring your Spark job

1. Open `http://localhost:8080` (Spark Master UI).
2. Under **"Running Applications"**, you should see your notebook's `appName`.
3. Click it to see stages, executors, and resource usage.
4. For ML training jobs, the **"Stages"** tab shows the map/reduce stages for fitting the `Pipeline`. Each `RandomForest` tree fit is a separate task.

### PySpark MLlib pattern in notebooks

The recommended pattern for training in JupyterHub:

```python
from pyspark.ml import Pipeline
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator
from pyspark.ml.feature import VectorAssembler
from pyspark.sql.functions import col
import mlflow.spark

FEATURE_COLUMNS = ["age", "total_orders", "lifetime_value", ...]

# Load from Iceberg
dataset = spark.sql("SELECT * FROM warehouse.analytics.churn_training_dataset")

# Cast to double (MLlib requires numeric types)
for fc in FEATURE_COLUMNS:
    dataset = dataset.withColumn(fc, col(fc).cast("double"))
dataset = dataset.withColumn("churn_label", col("churn_label").cast("double"))

# Build and train pipeline
assembler = VectorAssembler(inputCols=FEATURE_COLUMNS, outputCol="features")
rf = RandomForestClassifier(featuresCol="features", labelCol="churn_label", numTrees=50, seed=42)
pipeline = Pipeline(stages=[assembler, rf])

train_df, test_df = dataset.randomSplit([0.7, 0.3], seed=42)
model = pipeline.fit(train_df)

# Evaluate
predictions = model.transform(test_df)
accuracy = MulticlassClassificationEvaluator(
    labelCol="churn_label", predictionCol="prediction", metricName="accuracy"
).evaluate(predictions)

# Log the full Spark pipeline model to MLflow
with mlflow.start_run():
    mlflow.log_metric("accuracy", accuracy)
    mlflow.spark.log_model(model, artifact_path="spark-model")
```

### Stopping the Spark session

Always stop the Spark session when you are done to free cluster resources:

```python
spark.stop()
```

If you forget, the idle culler will eventually stop your JupyterHub server (after 1 hour of inactivity), which will also stop the Spark session.

---

## 4. Installing Additional Packages

### Pre-installed packages

The JupyterHub image (`jupyterhub/Dockerfile`) pre-installs these packages:

| Package | Version | Purpose |
|---|---|---|
| `pyspark` | 3.5.1 | Feature engineering and ML training via `pyspark.ml` |
| `pandas` | 2.2.3 | Data manipulation, collecting Spark results with `.toPandas()` |
| `numpy` | 1.26.4 | Numerical computing |
| `scikit-learn` | 1.5.2 | Available for prototyping; primary ML training uses `pyspark.ml` |
| `mlflow` | 3.10.1 | Experiment tracking; use `mlflow.spark.log_model()` for Spark models |
| `trino` | latest | Trino Python client |
| `pyarrow` | latest | Parquet I/O |
| `feast[aws]` | 0.40.1 | Feature store |
| `great_expectations` | 0.18.21 | Data validation |
| `evidently` | 0.4.16 | Drift detection |
| `matplotlib` | latest | Plotting |
| `seaborn` | latest | Statistical plots |
| `joblib` | latest | Model serialization |
| `psycopg2-binary` | latest | PostgreSQL driver |
| `pyiceberg[s3,pandas]` | latest | Iceberg Python client |

> **Note on sklearn vs pyspark.ml**: `scikit-learn` is available and useful for quick prototyping, but the platform's production training workflow uses `pyspark.ml`. PySpark MLlib scales across the cluster and saves models as MLflow Spark models, which MLServer serves via `mlserver_mlflow.MLflowRuntime`. If you prototype with sklearn, migrate to `pyspark.ml.Pipeline` before committing to the repo.

### Installing packages at runtime

If you need a package that is not pre-installed, install it in a notebook cell:

```python
!pip install --quiet xgboost
```

> **Warning**: Packages installed this way are **temporary**. They will be lost when your JupyterHub server restarts (due to idle culler timeout, container restart, or manual stop).

### Making packages permanent

To permanently add a package, edit `jupyterhub/Dockerfile`:

1. Open `jupyterhub/Dockerfile` in your editor.
2. Add the package to the `pip install` command:
   ```dockerfile
   RUN pip install --no-cache-dir \
       ...existing packages... \
       xgboost
   ```
3. Rebuild and restart:
   ```bash
   docker compose build jupyterhub
   docker compose up -d jupyterhub
   ```

---

## 5. What is Ephemeral vs Persistent

### Ephemeral (lost on restart)

- **Runtime pip installs**: Any `!pip install` in a notebook
- **In-memory variables**: DataFrames, models, etc. in running notebook kernels
- **Temporary files** written to `/tmp` or user home directories outside mounted volumes

### Persistent (survives restart)

- **Notebooks in `/srv/jupyterhub/notebooks/`**: This directory is mounted from `./notebooks/` in the repository. Anything saved here persists.
- **Files in mounted volumes**: Great Expectations configs (`/srv/jupyterhub/great_expectations/`), Evidently configs (`/srv/jupyterhub/evidently/`).
- **JupyterHub user database**: Stored in the `postgres-jupyterhub` container.

### Best practice

- **Do exploratory work** in notebooks inside JupyterHub.
- **Do not treat notebooks as permanent storage** for production code.
- **Commit production code** (dbt models, Feast definitions, DAGs, training scripts) to the repository.
- **Save important outputs** (models, CSVs, reports) to mounted volumes or push them to MinIO.

---

## 6. Idle Culler and Resource Management

### How the idle culler works

JupyterHub runs an idle culler service that:
- Checks every server for activity
- Stops servers that have been idle for **1 hour** (`--timeout=3600`)
- Limits maximum server age to **24 hours** (`--max-age=86400`)

When your server is stopped:
- All running kernels are terminated
- All in-memory variables are lost
- Spark sessions are terminated
- Temporary files are deleted
- But notebooks saved to mounted volumes are preserved

### Checking your server status

1. Go to `http://localhost:8888/hub/home`.
2. You should see your server listed as **"Running"**.
3. If it says **"Not running"**, click **"Start My Server"** to restart.

### Resource limits

Each user server has these limits (set in `jupyterhub_config.py`):

| Resource | Limit |
|---|---|
| Memory | 4 GB |
| CPU | 2 cores |

If your notebook or Spark job needs more resources:

1. Edit `jupyterhub/jupyterhub_config.py`:
   ```python
   c.Spawner.mem_limit = "8G"
   c.Spawner.cpu_limit = 4.0
   ```
2. Restart JupyterHub:
   ```bash
   docker compose restart jupyterhub
   ```

> **Note**: These limits apply to the JupyterHub process itself. The Spark session runs on the Spark cluster (separate containers), so Spark resource limits are controlled by `SPARK_WORKER_MEMORY` and `SPARK_WORKER_CORES` in `.env`.

---

## 7. What to Do in JupyterHub vs What to Commit

| Activity | Where to do it |
|---|---|
| Exploring data with SQL queries | JupyterHub notebook |
| Prototyping a model | JupyterHub notebook |
| Quick data visualizations | JupyterHub notebook |
| Testing Feast feature retrieval | JupyterHub notebook |
| Writing dbt models | Git repository (`dbt/retail/models/`) |
| Writing Feast definitions | Git repository (`feast/project/`) |
| Writing Airflow DAGs | Git repository (`airflow/dags/`) |
| Writing training scripts | Git repository (`bootstrap/` or custom directory) |
| Writing Dockerfiles | Git repository |
| Defining CI/CD workflows | Git repository |

### Rule of thumb

- **Notebooks are for exploration and one-off analysis.**
- **The repository is for anything that needs to be repeatable, versioned, or automated.**
- **Never rely on files inside JupyterHub that are not backed by a mounted volume or committed to the repository.**

---

## 8. Connecting to External Databases

If you need to connect to databases other than the demo-postgres, you can use the same pattern with environment variables.

### Example: connecting to a custom PostgreSQL database

In a JupyterHub notebook:

```python
import os
import pandas as pd
import psycopg2

conn = psycopg2.connect(
    host=os.environ.get("MY_DB_HOST", "my-database-host"),
    port=int(os.environ.get("MY_DB_PORT", "5432")),
    dbname=os.environ.get("MY_DB_NAME", "mydb"),
    user=os.environ.get("MY_DB_USER", "myuser"),
    password=os.environ.get("MY_DB_PASSWORD", "mypassword"),
)
df = pd.read_sql("SELECT * FROM my_table LIMIT 10", conn)
conn.close()
df
```

To make the environment variables available permanently, add them to `jupyterhub_config.py` under `c.Spawner.environment`:

```python
c.Spawner.environment = {
    ...existing variables...,
    "MY_DB_HOST": os.environ.get("MY_DB_HOST", "my-database-host"),
    "MY_DB_PORT": os.environ.get("MY_DB_PORT", "5432"),
}
```

Then add matching entries to your `.env` file and restart JupyterHub.

---

## 9. Troubleshooting

### JupyterHub won't start

```bash
docker compose logs jupyterhub --tail=50
```

Common causes:
- PostgreSQL backend (`postgres-jupyterhub`) is not healthy. Check with `docker compose ps postgres-jupyterhub`.
- Port 8888 is already in use. Check with `lsof -i :8888`.

### Notebook kernel keeps dying

This usually means the process ran out of memory. Check:
1. Are you loading large DataFrames? Use `df.head()` instead of `df` to avoid printing millions of rows.
2. Is your Spark session consuming all available memory? Stop it with `spark.stop()`.
3. Increase the memory limit in `jupyterhub_config.py`.

### Cannot connect to Spark

If `SparkSession.builder...getOrCreate()` hangs:
1. Check that Spark master is running: `docker compose ps spark-master`.
2. Check that the Spark worker is running: `docker compose ps spark-worker`.
3. Open `http://localhost:8080` — the master UI should show at least 1 alive worker.
4. If the worker has `0` available cores, another application is using all resources. Stop it from the Spark Master UI (click the application → **"kill"**).

### Cannot connect to Trino

If `trino.dbapi.connect()` fails:
1. Check that Trino is running: `docker compose ps trino`.
2. Open `http://localhost:8093` — the Trino UI should load.
3. From inside the JupyterHub container, Trino is at `trino:8080` (not `localhost:8093`).
