# Getting Started

## 1. Prepare secrets

```bash
cp .env.example .env
```

Edit `.env` and change the passwords. Generate these two values instead of keeping the defaults:

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Use the first value for `AIRFLOW_FERNET_KEY` and the second one for `MLFLOW_FLASK_SECRET_KEY` and `SUPERSET_SECRET_KEY`.

## 2. Build the custom images

```bash
docker compose build
```

This builds the custom images for Airflow, dbt, JupyterHub, MLflow, MLServer, Superset, Feast, and the bootstrap job.

## 3. Start the full stack

```bash
docker compose up -d
docker compose logs -f --tail=50 raw-bootstrap dbt-bootstrap platform-bootstrap feast-bootstrap quality-bootstrap
```

Wait for the one-shot bootstrap jobs to exit successfully. Together they do the initial learning setup:

- ingests raw tables from demo Postgres into Iceberg
- runs dbt models and tests through Trino
- generates dbt docs
- writes Feast offline feature files and materializes them
- builds Great Expectations Data Docs
- trains a churn model, logs a demo run to MLflow, and writes an MLServer model bundle
- creates an Evidently drift report

If `raw-bootstrap` fails, inspect its logs first. On smaller Docker Desktop allocations the bootstrap jobs can still fail because the Python, JVM, and query workload does not have enough memory. If you see memory-related failures, raise Docker memory and retry `docker compose up -d`.

## 4. Open the UIs

See [docs/ACCESS_AND_URLS.md](docs/ACCESS_AND_URLS.md) for the complete list.

The main starting points are:

- JupyterHub: `http://localhost:8888`
- Airflow: `http://localhost:8082`
- Superset: `http://localhost:8088`
- MLflow: `http://localhost:5000`
- Grafana: `http://localhost:3000`
- Great Expectations docs: `http://localhost:8091`
- Evidently report: `http://localhost:8092`

## 5. Follow the practice flow

Open [docs/PRACTICE_LAB.md](docs/PRACTICE_LAB.md). It walks through the stack as a learner:

1. read the shared foundations guide
2. choose the production-style or simpler repository-native lab
3. connect to a PostgreSQL source
4. inspect lakehouse ingestion and transformation outputs
5. validate data with dbt, Great Expectations, and the dbt docs site
6. inspect features in Feast
7. inspect training and experiment tracking in MLflow
8. inspect model serving through MLServer
9. inspect monitoring outputs in Evidently, Grafana, and Prometheus
10. use JupyterHub, Superset, CloudBeaver, and Trino as supported access layers

If you want repeatable notebook defaults, shared Spark settings, or VS Code connectivity, also read [docs/JUPYTERHUB_GUIDE.md](docs/JUPYTERHUB_GUIDE.md).

## Useful commands

```bash
docker compose ps
docker compose logs -f superset
docker compose logs -f trino
docker compose logs -f airflow-webserver
docker compose down
```
