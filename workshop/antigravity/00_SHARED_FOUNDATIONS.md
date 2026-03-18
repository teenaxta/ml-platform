# Shared Foundations

This document contains the common setup, architecture knowledge, and verification techniques that both Lab 1 and Lab 2 reference. Read it once before starting either lab.

---

## 1. Platform Architecture — Multi-Compose Setup

The platform runs across three separate systems:

| Compose / System | What it runs | How to start |
|---|---|---|
| `docker-compose.demo-postgres.yml` | Source database (simulates an external production DB) | `docker compose -f docker-compose.demo-postgres.yml up -d` |
| `docker-compose.yml` | Main platform (MinIO, Iceberg, Spark, Trino, dbt, Airflow, Feast, MLflow, MLServer, JupyterHub, Superset, Grafana, Prometheus, CloudBeaver, Great Expectations, Evidently) | `docker compose up -d` |
| Airbyte (via `abctl`) | Data ingestion from source databases into the lakehouse | `abctl local install` |

### Startup order

```bash
# 1. Create the shared network (if it doesn't exist yet)
docker network create mlplatform 2>/dev/null || true

# 2. Start the source database
docker compose -f docker-compose.demo-postgres.yml up -d

# 3. Start the main platform
docker compose up -d

# 4. Start Airbyte (first time only — subsequent starts are automatic)
abctl local install
```

### Verify everything is running

```bash
# Check source database
docker compose -f docker-compose.demo-postgres.yml ps

# Check main platform
docker compose ps --format "table {{.Name}}\t{{.Status}}"

# Check Airbyte
abctl local status
```

All main platform services should show `Up`. Bootstrap containers (`dbt-bootstrap`, `platform-bootstrap`, `feast-bootstrap`, `quality-bootstrap`) will show `Exited (0)` — they run once and stop.

---

## 2. Data Flow — How Data Moves Through the Platform

```
demo-postgres (source database)
      │
      ▼ Airbyte syncs tables via S3 Data Lake connector
Iceberg tables in MinIO (raw layer: iceberg.retail_raw.*)
      │
      ▼ dbt transforms via Trino
Iceberg analytics tables (iceberg.analytics.*)
      │
      ├──▶ PySpark reads marts, computes complex features, writes Parquet for Feast
      │
      ▼ Feast manages features
Feature store (registry in Postgres, online store in Postgres)
      │
      ▼ PySpark MLlib trains model in JupyterHub
Model training (RandomForest via pyspark.ml)
      │
      ├──▶ MLflow logs experiments, metrics, model artifacts
      │
      ▼ MLServer serves the model via REST API (after manual deployment)
Inference endpoint (http://localhost:8085/v2/models/<model-name>/infer)
      │
      ├──▶ Great Expectations validates data quality
      ├──▶ Evidently detects data drift
      │
      ▼ Airflow orchestrates the full pipeline on schedule
Dashboards: Superset (BI), Grafana (ops), Prometheus (metrics)
```

### Where each engine fits

| Engine | Role | When you use it |
|---|---|---|
| **Airbyte** | Automated data ingestion with CDC support, 300+ connectors | Pulling source tables into the lakehouse |
| **dbt + Trino** | SQL-based transformations, testing, documentation | Building staging and mart models |
| **Apache Spark** | Distributed compute for heavy feature engineering and ML training | Computing complex features that SQL can't handle; training models with PySpark MLlib |
| **Feast** | Feature store with point-in-time joins | Managing feature definitions and serving features |
| **MLflow** | Experiment tracking | Logging model parameters, metrics, and artifacts |
| **MLServer** | Model serving via REST/gRPC | Exposing trained models as API endpoints |

---

## 3. Service Map — Where Everything Lives

| Service | URL | Default Username | Default Password |
|---|---|---|---|
| Airbyte | `http://localhost:8000` | `airbyte` | `password` |
| JupyterHub | `http://localhost:8888` | `admin` | `JUPYTERHUB_ADMIN_PASSWORD` in `.env` |
| Airflow | `http://localhost:8082` | `admin` | `AIRFLOW_ADMIN_PASSWORD` in `.env` |
| Superset | `http://localhost:8088` | `admin` | `SUPERSET_ADMIN_PASSWORD` in `.env` |
| MLflow | `http://localhost:5000` | `admin` | `MLFLOW_ADMIN_PASSWORD` in `.env` |
| Grafana | `http://localhost:3000` | `admin` | `GRAFANA_ADMIN_PASSWORD` in `.env` |
| MinIO Console | `http://localhost:9001` | `MINIO_ROOT_USER` | `MINIO_ROOT_PASSWORD` |
| Spark Master UI | `http://localhost:8080` | none | none |
| Spark Worker UI | `http://localhost:8081` | none | none |
| Trino coordinator | `http://localhost:8093` | none | none |
| CloudBeaver | `http://localhost:8978` | set on first visit | set on first visit |
| dbt docs | `http://localhost:8090` | none | static site |
| Feast UI | `http://localhost:6567` | none | none |
| MLServer REST | `http://localhost:8085/v2` | none | none |
| Great Expectations docs | `http://localhost:8091` | none | static site |
| Evidently report | `http://localhost:8092` | none | static site |
| Prometheus | `http://localhost:9090` | none | none |

### Demo PostgreSQL (source database — separate compose)

- **From your host machine**: `localhost:5433`, database `retail_db`, user `analyst`, password `analyst123`
- **From inside platform containers**: host `demo-postgres`, port `5432`
- **From Airbyte**: `host.docker.internal:5433` (Airbyte runs in its own Kubernetes cluster)

---

## 4. MinIO — The Object Store

All Iceberg data, Feast parquet files, and MLflow artifacts live in MinIO.

### How to verify

1. Open `http://localhost:9001` and log in.
2. Click **Object Browser** → you should see these buckets:

| Bucket | Contents |
|---|---|
| `warehouse` | Iceberg tables (raw + analytics), Feast parquet exports |
| `mlflow-artifacts` | MLflow experiment artifacts |
| `feast-offline` | Feast offline store |
| `feast-registry` | Feast registry metadata |
| `monitoring` | Monitoring artifacts |

After Airbyte completes a sync, navigate to `warehouse` → `retail_raw/` — you should see folders for each table with `.parquet` files.

---

## 5. Trino — The Query Layer

Trino has two catalogs:

| Catalog | Backend | Contents |
|---|---|---|
| `iceberg` | Iceberg REST catalog → MinIO | Lakehouse tables: `retail_raw.*` and `analytics.*` |
| `postgresql` | demo-postgres | Original source tables: `public.*` |

### Verify Trino health

1. Open `http://localhost:8093`.
2. Look for **"Active Workers"** — should show `1`.
3. In JupyterHub, run:
   ```python
   cursor.execute("SHOW SCHEMAS FROM iceberg")
   ```
   Expected: `analytics`, `information_schema`, `retail_raw`.

---

## 6. Spark — Distributed Compute Engine

Spark is used for **feature engineering** (computing complex features post-dbt) and **ML model training** (via PySpark MLlib). It is NOT used for raw data ingestion — Airbyte handles that.

### Verify Spark health

1. Open `http://localhost:8080` (Master UI) — should show **1 worker** under "Alive Workers".
2. Open `http://localhost:8081` (Worker UI) — check **Cores Used** vs **Available**, **Memory Used** vs **Available**.
3. When a job is running, click its name in "Running Applications" → **Stages** tab to monitor progress.

---

## 7. Airbyte — Data Ingestion

Airbyte automatically syncs source database tables into the Iceberg lakehouse. Full setup instructions are in [AIRBYTE_SETUP.md](AIRBYTE_SETUP.md).

### Verify Airbyte health

1. Open `http://localhost:8000` and log in (username `airbyte`, password `password`).
2. Click **Connections** — your PostgreSQL → Iceberg connection should show last sync status.
3. All 8 tables should show "Succeeded" with correct row counts.

---

## 8. CloudBeaver — Database Browser

### First-time setup

1. Open `http://localhost:8978`, create an admin account.
2. Click **"New Connection"** → **PostgreSQL**.
3. Host: `demo-postgres`, Port: `5432`, Database: `retail_db`, User: `analyst`, Password: `analyst123`.
4. Browse: expand connection → `retail_db` → `public` → `Tables` — 8 tables, 3 views.

---

## 9. Airflow, MLflow, Feast, MLServer, Great Expectations, Evidently, Superset, Grafana, Prometheus

Verification procedures for each service remain as described in the individual lab documents. Each lab walks you through the exact page, menu, tab, and expected values for every service at the moment you need them.

---

## 10. Connection Details Quick Reference

### From inside containers (JupyterHub, Airflow, etc.)

| Target | Host | Port | User | Password |
|---|---|---|---|---|
| Demo Postgres | `demo-postgres` | `5432` | `analyst` | `analyst123` |
| Trino | `trino` | `8080` | `trino` | none |
| Spark Master | `spark-master` | `7077` | n/a | n/a |
| MLflow | `mlflow` | `5000` | from `.env` | from `.env` |
| MinIO (S3) | `minio` | `9000` | `MINIO_ROOT_USER` | `MINIO_ROOT_PASSWORD` |
| Feast Postgres | `postgres-feast` | `5432` | `feast` | `FEAST_DB_PASSWORD` |

### From your host machine

| Target | Host | Port |
|---|---|---|
| Demo Postgres | `localhost` | `5433` |
| Trino | `localhost` | `8093` |
| MinIO Console | `localhost` | `9001` |

---

## Next Step

1. First, set up Airbyte: follow [AIRBYTE_SETUP.md](AIRBYTE_SETUP.md).
2. Then start either:
   - **[Lab 1 — Production-Style Pipeline](01_LAB_PRODUCTION.md)**
   - **[Lab 2 — Repository-Native Pipeline](02_LAB_SIMPLE.md)**
