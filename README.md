# ML Platform — Quick Start

## What's in this folder

```
ml-platform/
├── docker-compose.yml              ← main stack (all services)
├── docker-compose.demo-postgres.yml← demo source database
├── .env.example                    ← copy to .env and edit
├── README.md                       ← you are here
│
├── spark/conf/spark-defaults.conf  ← Iceberg + MinIO config
├── jupyterhub/
│   ├── Dockerfile                  ← built at docker compose build
│   └── jupyterhub_config.py        ← user management, RBAC, idle culler
├── feast/
│   ├── Dockerfile                  ← built at docker compose build
│   ├── entrypoint.sh
│   └── project/
│       ├── feature_store.yaml      ← Feast config (MinIO + Postgres)
│       └── features.py             ← all feature definitions (edit these)
├── mlserver/
│   ├── settings.json
│   └── models/                     ← drop trained model folders here
├── airflow/
│   └── dags/retail_pipeline.py     ← example DAG
├── dbt/                            ← put your dbt project here
├── notebooks/
│   └── 01_ingest_and_explore.py    ← example PySpark notebook
└── demo-postgres/
    └── init.sql                    ← retail dataset (auto-loaded)
```

---

## First-time setup (5 steps)

### 1. Copy and edit the environment file

```bash
cp .env.example .env
```

Open `.env` and change all passwords. For the Fernet key run:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the output as `AIRFLOW_FERNET_KEY` in `.env`.

### 2. Build custom images

```bash
docker compose build
```

This builds JupyterHub (with PySpark + ML libs) and Feast (with all deps).
Takes 3–5 minutes on first run.

### 3. Start the main stack

```bash
docker compose up -d
```

Watch startup:

```bash
docker compose logs -f --tail=30
```

Wait until you see `airflow-webserver` show **healthy** and `feast` show
**Feast feature server started**.

### 4. Start the demo database

```bash
docker compose -f docker-compose.demo-postgres.yml up -d
```

### 5. Open the UIs

| Service        | URL                          | Login                        |
|----------------|------------------------------|------------------------------|
| JupyterHub     | http://localhost:8888        | admin / see .env             |
| Airflow        | http://localhost:8082        | admin / see .env             |
| MinIO Console  | http://localhost:9001        | mlplatform / see .env        |
| CloudBeaver    | http://localhost:8978        | create on first visit        |
| Spark Master   | http://localhost:8080        | no login                     |
| MLServer REST  | http://localhost:8085/v2     | no login                     |

---

## Connect your real Postgres databases

Open **CloudBeaver** at http://localhost:8978.  
New Connection → PostgreSQL → fill in your server IP, port, database, user, password.

For automated daily ingestion, point Airbyte at each database and write
to `s3://warehouse/raw/<db_name>/` on MinIO.

For one-off reads in notebooks, use Spark JDBC:

```python
df = spark.read.jdbc(
    "jdbc:postgresql://YOUR_IP:5432/YOUR_DB",
    "public.your_table",
    properties={"user": "...", "password": "...", "driver": "org.postgresql.Driver"}
)
```

---

## Add JupyterHub users

1. Open http://localhost:8888/hub/admin
2. Log in as admin
3. Click **Add Users** → enter usernames → click Add
4. Users log in and set their own password

Or users self-register at http://localhost:8888/hub/signup — you then
approve them in the admin panel.

---

## Deploy a model to MLServer

1. Save your model with `joblib.dump(model, "model.joblib")`
2. Create `mlserver/models/my-model/model-settings.json`:
   ```json
   {
     "name": "my-model",
     "implementation": "mlserver_sklearn.SKLearnModel",
     "parameters": { "uri": "./model.joblib", "version": "v1" }
   }
   ```
3. Copy `model.joblib` into `mlserver/models/my-model/`
4. `docker compose restart mlserver`
5. Test: `curl http://localhost:8085/v2/models/my-model`

---

## Useful commands

```bash
# Status of all containers
docker compose ps

# Tail logs for one service
docker compose logs -f feast
docker compose logs -f airflow-scheduler

# Run dbt (once you've placed a project in ./dbt/)
docker compose exec dbt bash -c "cd /opt/dbt/retail && dbt run"
docker compose exec dbt bash -c "cd /opt/dbt/retail && dbt docs generate && dbt docs serve --port 8080"
# Then open http://localhost:8090

# Re-apply Feast feature definitions after editing features.py
docker compose exec feast feast -c /opt/feast/project apply

# Stop everything (keeps data volumes)
docker compose down
docker compose -f docker-compose.demo-postgres.yml down

# Wipe everything including data (destructive!)
docker compose down -v
```
