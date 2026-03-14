# ML Platform — Getting Started Guide

## Directory layout

After cloning / extracting, your project should look like this:

```
ml-platform/
├── docker-compose.yml
├── .env.example          ← copy to .env and fill in secrets
├── .env                  ← never commit this
├── spark/
│   └── conf/
│       └── spark-defaults.conf
├── mlserver/
│   ├── settings.json
│   └── models/           ← drop model dirs here
├── airflow/
│   ├── dags/             ← your Airflow DAGs
│   ├── logs/
│   └── plugins/
├── dbt/                  ← your dbt project
├── feast/                ← your Feast project
└── notebooks/            ← JupyterLab work directory
```

---

## 1. First-time setup

```bash
# 1. Copy and edit the environment file
cp .env.example .env
# Edit .env — change every password and generate the Fernet key:
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Paste the output as AIRFLOW_FERNET_KEY in .env

# 2. Create required local directories
mkdir -p airflow/dags airflow/logs airflow/plugins \
         notebooks dbt feast \
         mlserver/models spark/conf

# 3. Pull all images first (good to do on a fast connection)
docker compose pull

# 4. Start everything
docker compose up -d

# 5. Watch startup progress
docker compose logs -f --tail=50
```

---

## 2. Service URLs

| Service | URL | Credentials |
|---|---|---|
| **MinIO Console** | http://localhost:9001 | `.env` MINIO_ROOT_USER / PASSWORD |
| **JupyterLab** | http://localhost:8888 | token from `.env` JUPYTER_TOKEN |
| **Spark Master UI** | http://localhost:8080 | — |
| **Spark Worker UI** | http://localhost:8081 | — |
| **Airflow** | http://localhost:8082 | admin / AIRFLOW_ADMIN_PASSWORD |
| **MLServer REST** | http://localhost:8085/v2 | — |
| **MLServer docs** | http://localhost:8085/v2/docs | — |
| **CloudBeaver** | http://localhost:8978 | set on first login |
| **Iceberg REST** | http://localhost:8181/v1/namespaces | — |

---

## 3. Connecting your external PostgreSQL databases

### Option A — CloudBeaver (replaces PgAdmin, web UI)

1. Open http://localhost:8978
2. Create an admin account on first launch
3. Click **New Connection** → **PostgreSQL**
4. Fill in:
   - Host: your Postgres server IP or hostname
   - Port: 5432
   - Database: your database name
   - Username / Password: your Postgres credentials
5. Click **Test Connection** → **Finish**

Repeat for each of your 4–5 databases. You can now run SQL queries,
browse schemas, and export results — all from a browser, no desktop
client needed.

> **Network note:** CloudBeaver runs inside Docker. Your Postgres server
> must be reachable from the Docker host. If your Postgres is on the
> same machine, use the host's LAN IP (not `localhost`) as the host.
> If it's on a separate server, use that server's IP.

### Option B — Connect Airbyte to Postgres (automated ingestion)

Airbyte is a separate deployment (too large for this compose file).
Deploy it alongside this stack:

```bash
git clone https://github.com/airbytehq/airbyte.git
cd airbyte && ./run-ab-platform.sh
# UI at http://localhost:8000
```

Then configure a **PostgreSQL Source** pointing at each of your databases
and a **MinIO / S3 Destination** writing to `s3://warehouse/raw/<db_name>/`
as Parquet files. Airbyte handles incremental syncs automatically.

### Option C — Direct PySpark connection from notebooks

For one-off reads inside JupyterLab without Airbyte:

```python
# In a notebook cell
jdbc_url = "jdbc:postgresql://YOUR_POSTGRES_IP:5432/YOUR_DB"

df = spark.read \
    .format("jdbc") \
    .option("url", jdbc_url) \
    .option("dbtable", "public.your_table") \
    .option("user", "your_user") \
    .option("password", "your_password") \
    .option("driver", "org.postgresql.Driver") \
    .load()

df.show(5)
```

Then write it to your Iceberg lakehouse:

```python
df.writeTo("warehouse.raw.your_table").createOrReplace()
```

---

## 4. Toy example — end-to-end test

This walks through the entire stack with a simple dataset.

### Step 1 — Create an Iceberg table in JupyterLab

Open http://localhost:8888, create a new notebook, and run:

```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("IcebergTest") \
    .config("spark.hadoop.fs.s3a.access.key", "mlplatform") \
    .config("spark.hadoop.fs.s3a.secret.key", "change_me_minio_123") \
    .getOrCreate()

# Create a namespace and a test table
spark.sql("CREATE NAMESPACE IF NOT EXISTS warehouse.toy_example")

spark.sql("""
    CREATE TABLE IF NOT EXISTS warehouse.toy_example.customers (
        customer_id BIGINT,
        age         INT,
        spend_last_30d DOUBLE,
        churn       INT
    ) USING iceberg
""")

# Insert some toy data
spark.sql("""
    INSERT INTO warehouse.toy_example.customers VALUES
    (1, 32, 450.0, 0),
    (2, 45, 120.0, 1),
    (3, 28, 980.0, 0),
    (4, 60, 30.0,  1),
    (5, 35, 670.0, 0)
""")

spark.sql("SELECT * FROM warehouse.toy_example.customers").show()
```

Check MinIO at http://localhost:9001 → bucket `warehouse` → you should
see Parquet files under `toy_example/customers/`.

### Step 2 — Write a dbt model

```bash
# Initialise a dbt project inside the container
docker compose exec dbt dbt init toy_project
```

Edit `dbt/toy_project/models/high_value_customers.sql`:

```sql
SELECT
    customer_id,
    age,
    spend_last_30d,
    CASE WHEN spend_last_30d > 400 THEN 1 ELSE 0 END AS is_high_value
FROM warehouse.toy_example.customers
WHERE churn = 0
```

Run it:

```bash
docker compose exec dbt bash -c "cd /opt/dbt/toy_project && dbt run"
```

### Step 3 — Train a model in JupyterLab

```python
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import mlserver
import joblib, os

# Read from Iceberg
df = spark.sql("SELECT * FROM warehouse.toy_example.customers").toPandas()

X = df[["age", "spend_last_30d"]]
y = df["churn"]
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)

print("Accuracy:", model.score(X_test, y_test))

# Save the model for MLServer
os.makedirs("work/churn-model", exist_ok=True)
joblib.dump(model, "work/churn-model/model.joblib")
```

### Step 4 — Deploy to MLServer

Create `notebooks/churn-model/model-settings.json`:

```json
{
    "name": "churn-model",
    "implementation": "mlserver_sklearn.SKLearnModel",
    "parameters": {
        "uri": "./model.joblib",
        "version": "v1"
    }
}
```

Copy the model to the MLServer models directory and reload:

```bash
cp -r notebooks/churn-model mlserver/models/
docker compose restart mlserver
```

Test the endpoint:

```bash
curl -X POST http://localhost:8085/v2/models/churn-model/infer \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": [{
      "name": "predict",
      "shape": [1, 2],
      "datatype": "FP64",
      "data": [[35, 650.0]]
    }]
  }'
```

You should get back a prediction (`0` = not churned, `1` = churned).

### Step 5 — Schedule with Airflow

Create `airflow/dags/toy_pipeline.py`:

```python
from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime

with DAG("toy_pipeline", start_date=datetime(2024, 1, 1),
         schedule="@daily", catchup=False) as dag:

    ingest = BashOperator(
        task_id="ingest_postgres",
        bash_command="echo 'Airbyte sync would trigger here via API call'"
    )

    transform = BashOperator(
        task_id="dbt_run",
        bash_command="docker exec dbt bash -c 'cd /opt/dbt/toy_project && dbt run'"
    )

    ingest >> transform
```

Open Airflow at http://localhost:8082, find `toy_pipeline`, toggle it on,
and trigger a manual run to confirm the pipeline works.

---

## 5. Useful operational commands

```bash
# View all running services and their status
docker compose ps

# Tail logs for a specific service
docker compose logs -f jupyter
docker compose logs -f airflow-scheduler

# Restart a single service without touching others
docker compose restart mlserver

# Scale Spark workers (e.g. add a second worker)
docker compose up -d --scale spark-worker=2

# Open a shell inside any container
docker compose exec jupyter bash
docker compose exec dbt bash
docker compose exec airflow-webserver bash

# Run dbt commands
docker compose exec dbt bash -c "cd /opt/dbt/<your_project> && dbt run"
docker compose exec dbt bash -c "cd /opt/dbt/<your_project> && dbt test"
docker compose exec dbt bash -c "cd /opt/dbt/<your_project> && dbt docs generate && dbt docs serve --port 8080"
# Then visit http://localhost:8090 for dbt docs

# Stop everything (keeps volumes)
docker compose down

# Stop and wipe all data (destructive!)
docker compose down -v
```

---

## 6. Troubleshooting

### "password authentication failed for user airflow" (or other Postgres users)

This happens when the password in `.env` was **changed after** the Postgres container was first created. Postgres sets the password only on first init; existing data volumes keep the old password.

**Fix — reset the affected database volume and start again:**

```bash
# Stop everything (must stop before removing the volume)
docker compose down

# Remove only the Airflow DB volume
# Volume name = <project-name>_postgres_airflow_data (project name = directory name, e.g. ml-platform)
docker volume rm ml-platform_postgres_airflow_data

# Start again (Postgres will re-init with current .env passwords)
docker compose up -d
```

To see your actual volume names: `docker volume ls | grep postgres`. Then remove the one you need, e.g. for other DBs:

- `ml-platform_postgres_jupyterhub_data`
- `ml-platform_postgres_feast_data`
- `ml-platform_postgres_mlflow_data`

**Avoid:** After the first successful `docker compose up`, do not change `*_DB_PASSWORD` (or MinIO credentials) in `.env` unless you are okay resetting the corresponding volume as above.

### MinIO "container is unhealthy" or minio-init never finishes

The MinIO server image does not include the `mc` client, so a healthcheck that used `mc` was removed. If minio-init still fails, ensure `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` in `.env` match in both the `minio` and `minio-init` services (no typos, no extra spaces). Then:

```bash
docker compose down
docker compose up -d
docker compose logs -f minio-init
```

---

## 7. GPU access for Spark / Jupyter

If your server has NVIDIA GPUs and you want them available inside
the Spark worker or Jupyter containers, add this to each relevant
service in docker-compose.yml:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

Also install `nvidia-container-toolkit` on the host:

```bash
sudo apt install nvidia-container-toolkit
sudo systemctl restart docker
```

---

## 8. Connecting from outside the server

All services bind to `0.0.0.0` inside Docker. From any machine on your
network, replace `localhost` with your GPU server's IP address.

For example:
- MinIO Console:  http://192.168.1.X:9001
- JupyterLab:     http://192.168.1.X:8888?token=YOUR_TOKEN
- Airflow:        http://192.168.1.X:8082
- CloudBeaver:    http://192.168.1.X:8978

Consider putting Nginx in front of these services and enabling HTTPS
before exposing them beyond your LAN.
