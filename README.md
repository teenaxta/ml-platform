# ML Platform

This repo is now a local teaching stack for an end-to-end ML and analytics platform. It includes:

- data source and storage: demo Postgres, MinIO, Iceberg REST, Spark
- analytics and orchestration: Trino, dbt, Airflow
- feature and experiment tooling: Feast, MLflow
- serving and monitoring: MLServer, Great Expectations, Evidently
- BI and observability: Superset, Prometheus, Grafana, CloudBeaver, JupyterHub

The stack is built around one retail/churn demo storyline so you can follow the same data through ingestion, transformation, feature engineering, validation, experimentation, monitoring, and dashboards.

## Start here

1. Copy `.env.example` to `.env` and change the passwords.
2. Run `docker compose build`.
3. Run `docker compose up -d`.
4. Watch the one-shot bootstrap jobs finish: `raw-bootstrap`, `dbt-bootstrap`, `platform-bootstrap`, `feast-bootstrap`, and `quality-bootstrap`.

## Main docs

- [GETTING_STARTED.md](GETTING_STARTED.md)
- [docs/STACK_COMPONENTS.md](docs/STACK_COMPONENTS.md)
- [docs/PRACTICE_LAB.md](docs/PRACTICE_LAB.md)
- [docs/PRACTICE_LAB_FOUNDATIONS.md](docs/PRACTICE_LAB_FOUNDATIONS.md)
- [docs/PRACTICE_LAB_1_PRODUCTION.md](docs/PRACTICE_LAB_1_PRODUCTION.md)
- [docs/PRACTICE_LAB_2_REPO_NATIVE.md](docs/PRACTICE_LAB_2_REPO_NATIVE.md)
- [docs/JUPYTERHUB_GUIDE.md](docs/JUPYTERHUB_GUIDE.md)
- [docs/ACCESS_AND_URLS.md](docs/ACCESS_AND_URLS.md)

## Important repo paths

- `docker-compose.yml`: full local platform
- `demo-postgres/init.sql`: raw source dataset and operational tables
- `dbt/retail/`: dbt project for analytics marts
- `bootstrap/seed_demo.py`: startup seeding flow shared by bootstrap and Airflow
- `airflow/dags/retail_pipeline.py`: scheduled orchestration entry point
- `notebooks/`: walkthrough notebooks for Spark, Trino, dbt-adjacent exploration, and model training
