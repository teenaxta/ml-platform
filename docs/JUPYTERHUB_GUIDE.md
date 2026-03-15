# JupyterHub Guide

This guide explains how to make the JupyterHub setup repeatable for every developer instead of asking each person to re-enter Spark, Trino, MLflow, or source database settings in every notebook.

## How the environment should be split

Use these layers on purpose:

- `docker-compose.yml` -> define the shared service endpoints, credentials, and runtime defaults for the `jupyterhub` container
- `jupyterhub/jupyterhub_config.py` -> forward those values into every spawned user server through `c.Spawner.environment`
- `spark/conf/spark-defaults.conf` -> keep cluster-wide Spark defaults here when they should apply to all Spark jobs
- notebook code -> read from environment variables and only keep true notebook logic in the file
- `jupyterhub/Dockerfile` -> add Python packages or system packages that every user should have

That split gives you one place for platform defaults and keeps notebooks portable.

## What is already centralized in this repo

The JupyterHub service now passes these defaults into user sessions:

- Spark master: `SPARK_MASTER`
- Trino connection: `TRINO_HOST`, `TRINO_PORT`, `TRINO_USER`, `TRINO_CATALOG`, `TRINO_SCHEMA`
- MLflow connection: `MLFLOW_TRACKING_URI`, `MLFLOW_TRACKING_USERNAME`, `MLFLOW_TRACKING_PASSWORD`
- Iceberg catalog connection: `ICEBERG_JDBC_URI`, `ICEBERG_JDBC_USER`, `ICEBERG_JDBC_PASSWORD`
- demo PostgreSQL connection: `DEMO_POSTGRES_HOST`, `DEMO_POSTGRES_PORT`, `DEMO_POSTGRES_DB`, `DEMO_POSTGRES_USER`, `DEMO_POSTGRES_PASSWORD`
- object storage and Java defaults: `AWS_*`, `AWS_S3_ENDPOINT`, `JAVA_HOME`

That means a notebook can do this:

```python
import os

trino_host = os.environ["TRINO_HOST"]
mlflow_uri = os.environ["MLFLOW_TRACKING_URI"]
postgres_db = os.environ["DEMO_POSTGRES_DB"]
```

instead of hardcoding `trino`, `demo-postgres`, `retail_db`, or `http://mlflow:5000` in every file.

## How to make notebook configuration repeatable

When you want a new default for all JupyterHub users:

1. Add or update the variable in `docker-compose.yml` under the `jupyterhub.environment` block.
2. Forward it in `jupyterhub/jupyterhub_config.py` inside `c.Spawner.environment`.
3. Update notebook code to read `os.environ.get(...)` instead of embedding the literal value.
4. Restart JupyterHub:

```bash
docker compose up -d --build jupyterhub
```

If you change only `docker-compose.yml` or `jupyterhub/jupyterhub_config.py`, a restart is enough:

```bash
docker compose up -d jupyterhub
```

## Where Spark settings should live

Put Spark defaults in the right place based on scope:

- put cluster-wide settings in [spark/conf/spark-defaults.conf](/Users/rohan/Projects/netsol/ml-platform/spark/conf/spark-defaults.conf)
- put Jupyter-only environment values in [jupyterhub/jupyterhub_config.py](/Users/rohan/Projects/netsol/ml-platform/jupyterhub/jupyterhub_config.py)
- avoid keeping connector hosts, passwords, or catalog URIs inline in notebooks unless they are intentionally one-off

Examples of settings that belong in `spark-defaults.conf`:

- catalog wiring
- S3 or MinIO endpoint defaults
- serializer settings
- shuffle partition defaults
- Spark SQL extensions

Examples of settings that belong in JupyterHub environment variables:

- source database host and credentials
- Trino host, port, and default catalog
- MLflow tracking URI
- per-environment endpoints that notebooks read directly

## How to add packages for every developer

If everyone using JupyterHub should have a package, add it to [jupyterhub/Dockerfile](/Users/rohan/Projects/netsol/ml-platform/jupyterhub/Dockerfile) and rebuild the image. Do not rely on ad hoc `pip install` inside a notebook if you want the environment to stay repeatable.

Typical workflow:

```bash
docker compose build jupyterhub
docker compose up -d jupyterhub
```

## How to use JupyterHub in this repo

The usual flow is:

1. Open JupyterHub at `http://localhost:8888`.
2. Sign in and start your server.
3. Open files from `/srv/jupyterhub/notebooks`.
4. Use the shared environment variables instead of editing service endpoints in the notebook.
5. Use Spark for ingestion or large transformations, Trino for SQL access, and MLflow for experiment logging.

The notebooks also have access to:

- `/srv/jupyterhub/great_expectations`
- `/srv/jupyterhub/evidently`
- `/usr/local/spark/conf/spark-defaults.conf`

## How to connect VS Code to JupyterHub

The simplest path is to use VS Code as a client for the Jupyter server that JupyterHub starts for your user.

1. Log into JupyterHub in the browser and start your user server.
2. In JupyterLab, open a terminal and run:

```bash
jupyter server list
```

3. Copy the full single-user server URL from that output.
4. In VS Code, install the `Python` and `Jupyter` extensions.
5. Open the Command Palette and run `Jupyter: Specify Jupyter Server for Connections`.
6. Choose `Existing`.
7. Paste the URL from `jupyter server list`.

After that, VS Code can run notebooks against the same JupyterHub-backed kernel environment.

If the pasted URL does not work from VS Code, first confirm that your browser session can open the same single-user server URL directly.

## `.py` versus `.ipynb` in this repo

The current files in [notebooks](/Users/rohan/Projects/netsol/ml-platform/notebooks) are intentionally plain `.py` walkthrough scripts, not `.ipynb` notebooks.

That is reasonable here because `.py` files:

- diff cleanly in Git
- are easier to review
- avoid noisy notebook metadata
- work well for scripted walkthroughs of the platform

Use `.ipynb` when you specifically want:

- rich cell outputs committed with the file
- markdown cells inside the document
- widget-heavy exploratory work
- a more notebook-native VS Code or JupyterLab authoring experience

So the short answer is: no, they do not have to be `.ipynb`. In this repo the `.py` choice is consistent with the documented "notebook-style walkthrough" approach.

If you want both clean Git diffs and real notebook files, the next step would be to adopt Jupytext and keep paired `.ipynb` and `.py` files.
