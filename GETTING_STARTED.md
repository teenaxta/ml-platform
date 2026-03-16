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

Use the first value for `AIRFLOW_FERNET_KEY` and the second for `MLFLOW_FLASK_SECRET_KEY` and `SUPERSET_SECRET_KEY`.

---

## 2. Create the shared Docker network

All compose files share a single Docker network. Create it once before starting anything:

```bash
docker network create mlplatform 2>/dev/null || true
```

---

## 3. Start the source database

The demo PostgreSQL database runs in its own compose file so it can be started and stopped independently of the main platform.

```bash
docker compose -f docker-compose.demo-postgres.yml up -d
```

Verify it is healthy:

```bash
docker compose -f docker-compose.demo-postgres.yml ps
```

The `demo-postgres` container should show `healthy`.

---

## 4. Install and start Airbyte

Airbyte is the data ingestion layer. It replaced the old `raw-bootstrap` job and syncs source tables from `demo-postgres` into the Iceberg lakehouse.

> **Why not a docker-compose file?** Airbyte deprecated Docker Compose after v1.0 (August 2024). The official self-hosted method is `abctl`, which uses a local Kubernetes cluster under the hood.

Install `abctl` (macOS):

```bash
brew tap airbytehq/tap
brew install abctl
```

Install `abctl` (Linux):

```bash
curl -LsfS https://get.airbyte.com | bash -
```

Start Airbyte:

```bash
abctl local install
```

This takes 3–10 minutes on first run. When complete, Airbyte is available at `http://localhost:8000` (username `airbyte`, password `password`).

For full configuration instructions (PostgreSQL source, Iceberg/MinIO destination, running the first sync), follow [workshop/antigravity/AIRBYTE_SETUP.md](workshop/antigravity/AIRBYTE_SETUP.md).

---

## 5. Build the custom images

```bash
docker compose build
```

This builds the custom images for Airflow, dbt, JupyterHub, MLflow, MLServer, Superset, Feast, and the bootstrap job.

---

## 6. Start the main platform

```bash
docker compose up -d
docker compose logs -f --tail=50 dbt-bootstrap platform-bootstrap feast-bootstrap quality-bootstrap
```

Wait for the one-shot bootstrap jobs to exit successfully. Together they:

- Run dbt models and tests through Trino
- Generate dbt docs
- Use PySpark to read Iceberg marts and write Feast offline feature files to MinIO
- Train a churn model with PySpark MLlib, log the run to MLflow, and write the MLflow Spark model bundle for MLServer
- Materialize Feast features into the online store (Postgres)
- Build Great Expectations Data Docs
- Create an Evidently drift report

> **Note**: `platform-bootstrap` requires that Airbyte has already synced raw data into Iceberg (`iceberg.retail_raw.*`). Run an Airbyte sync from the UI (step 4) before starting the platform, or the `dbt-bootstrap` step will fail because the source tables do not exist yet.

If bootstrap jobs fail due to memory pressure, raise Docker Desktop memory and retry `docker compose up -d`.

---

## 7. Open the UIs

See [docs/ACCESS_AND_URLS.md](docs/ACCESS_AND_URLS.md) for the complete list.

The main starting points are:

| UI | URL | Notes |
|---|---|---|
| Airbyte | `http://localhost:8000` | Configure ingestion syncs |
| JupyterHub | `http://localhost:8888` | PySpark notebooks, feature exploration |
| Airflow | `http://localhost:8082` | Pipeline orchestration |
| Superset | `http://localhost:8088` | BI dashboards over Trino |
| MLflow | `http://localhost:5000` | Experiment tracking, PySpark MLlib models |
| Grafana | `http://localhost:3000` | Ops dashboards |
| Spark Master UI | `http://localhost:8080` | Monitor Spark jobs |
| Great Expectations | `http://localhost:8091` | Data quality reports |
| Evidently | `http://localhost:8092` | Drift reports |

---

## 8. Follow the practice flow

Open the workshop documents in `workshop/antigravity/`:

1. Read [00_SHARED_FOUNDATIONS.md](workshop/antigravity/00_SHARED_FOUNDATIONS.md) — architecture, startup order, service map
2. Set up Airbyte: follow [AIRBYTE_SETUP.md](workshop/antigravity/AIRBYTE_SETUP.md)
3. Choose your lab:
   - [01_LAB_PRODUCTION.md](workshop/antigravity/01_LAB_PRODUCTION.md) — production-style, build everything manually
   - [02_LAB_SIMPLE.md](workshop/antigravity/02_LAB_SIMPLE.md) — repository-native, use existing scripts

---

## Useful commands

```bash
# Status
docker compose ps
docker compose -f docker-compose.demo-postgres.yml ps
abctl local status

# Logs
docker compose logs -f airflow-webserver
docker compose logs -f trino
docker compose logs -f spark-master
docker compose logs -f jupyterhub

# Restart a service
docker compose restart mlserver

# Full teardown (keeps volumes)
docker compose down
docker compose -f docker-compose.demo-postgres.yml down

# Full teardown including volumes
docker compose down -v
docker compose -f docker-compose.demo-postgres.yml down -v
```
