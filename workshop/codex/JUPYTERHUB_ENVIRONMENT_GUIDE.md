# JupyterHub Environment Guide

Use this guide when the lab tells you to work in JupyterHub. This guide is about environment setup, Spark access, package management, and safe usage. It is not a place to hardcode one permanent database target.

## 1. Log in and confirm your server is using the expected environment

### Goal of this section

Start a notebook server and confirm that the expected platform variables are available inside it.

### What you will create or change

- a running JupyterHub user server
- optionally a notebook or terminal session

### Exact steps

1. Open `http://localhost:8888`.
2. Log in with the JupyterHub admin or your own user.
3. Click `Start My Server`.
4. When JupyterLab opens, click `File -> New -> Terminal`.
5. Run:

```bash
env | egrep 'SPARK_MASTER|TRINO_HOST|TRINO_PORT|TRINO_CATALOG|TRINO_SCHEMA|MLFLOW_TRACKING_URI|DEMO_POSTGRES_HOST|AWS_S3_ENDPOINT'
```

Expected output includes keys like:

```text
SPARK_MASTER=spark://spark-master:7077
TRINO_HOST=trino
TRINO_PORT=8080
TRINO_CATALOG=iceberg
TRINO_SCHEMA=analytics
MLFLOW_TRACKING_URI=http://mlflow:5000
DEMO_POSTGRES_HOST=demo-postgres
AWS_S3_ENDPOINT=http://minio:9000
```

### What CI/CD or the platform does next

Nothing. This is a runtime verification step.

### How to verify

Healthy looks like all variables print successfully.

Broken looks like:

- one or more variables are missing
- `SPARK_MASTER` is blank
- `TRINO_HOST` is blank

If they are missing, open `jupyterhub/jupyterhub_config.py` and check `c.Spawner.environment`.

### Common mistakes

- Hardcoding hostnames directly into notebooks without first checking the environment variables.
- Assuming notebook state is permanent. The notebook workspace is not your deployment source of truth.

## 2. Know where to work and where not to work

### Goal of this section

Separate exploratory work from code that belongs in Git.

### What you will create or change

- temporary notebooks or scratch files
- no permanent deployment assets yet

### Exact steps

Use these locations deliberately:

| Where | Use it for | Do not use it for |
|---|---|---|
| Jupyter notebook files under your JupyterLab home | scratch analysis, quick SQL checks, one-off charts | the final production copy of dbt models, Feast definitions, DAGs, or workflow YAML |
| repository files under the checked-out workspace | code that must be committed | short-lived scratch cells |
| `File -> New -> Terminal` | environment checks and small validation commands | editing deployment files with no later commit |

Rule to follow:

- if the file is part of the real workflow, move it into the repository and commit it
- if the file is just a temporary exploration, keep it in JupyterHub and delete it later

### What CI/CD or the platform does next

Only repository files are picked up by CI/CD. Notebook scratch work is ignored until you turn it into real files under version control.

### How to verify

Healthy practice:

- your permanent code lives in the repository
- your temporary notebook cells are only for exploration

Broken practice:

- the only copy of your SQL or Python exists in a notebook
- you cannot point to a Git-tracked file for the logic you intend to deploy

### Common mistakes

- Treating a notebook as the permanent home of the training pipeline.
- Editing repository code inside JupyterHub and then forgetting to commit it.

## 3. Verify Spark before you submit notebook work

### Goal of this section

Confirm that the notebook can reach Spark and that the Spark cluster is healthy before you run heavier work.

### What you will create or change

- a short Spark verification snippet

### Exact steps

1. In JupyterLab, click `File -> New -> Notebook`.
2. Choose the default Python kernel.
3. Paste this code into the first cell:

```python
import os
from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .appName("JupyterHubSparkCheck")
    .master(os.environ["SPARK_MASTER"])
    .getOrCreate()
)

print(spark.sparkContext.master)
print(spark.range(5).toPandas())
```

4. Run the cell.
5. Open `http://localhost:8080`.
6. Click the new application name.
7. Open `Executors` and `Stages`.

### What CI/CD or the platform does next

Nothing. This is interactive validation only.

### How to verify

Healthy looks like:

- the notebook prints `spark://spark-master:7077`
- a small DataFrame renders with numbers `0` through `4`
- the Spark master UI shows a new application
- the worker remains `ALIVE`

Broken looks like:

- the notebook cell hangs for a long time
- the master UI shows no application
- the application shows failed stages

If it breaks:

1. Open `http://localhost:8080`.
2. Click the failing app.
3. Read the failed stage details.
4. If the cluster shows zero available cores, wait for other work to finish or reduce your notebook job.

### Common mistakes

- Calling `.toPandas()` on a large DataFrame.
- Blaming Spark code first when the worker is actually missing from the cluster.

## 4. Manage packages the correct way

### Goal of this section

Put shared dependencies in the image, not in ad hoc per-session install commands.

### What you will create or change

- `jupyterhub/Dockerfile` when a package must exist for every user
- optionally `docker-compose.yml` or `jupyterhub/jupyterhub_config.py` if environment variables must be forwarded

### Exact steps

1. If every user needs a new Python package, edit `jupyterhub/Dockerfile`.
2. Add the package to the `pip install` line.
3. Rebuild the image:

```bash
docker compose build jupyterhub
docker compose up -d jupyterhub
```

4. Log back into JupyterHub.
5. Open a terminal.
6. Run:

```bash
python -c "import pandas, trino, mlflow; print('imports ok')"
```

If the package is only for a short experiment, do not bake it into the image. Use a temporary notebook install and then remove that dependency from your working notes before you commit anything.

### What CI/CD or the platform does next

If `jupyterhub/Dockerfile` changes are committed, CI/CD rebuilds the JupyterHub image and deploys it. Every future user server then starts with the same package set.

### How to verify

Healthy looks like:

- the rebuilt `jupyterhub` service is `Up`
- the import command succeeds in a fresh user server

Broken looks like:

- the build fails
- the container restarts repeatedly
- imports still fail in a fresh server

### Common mistakes

- Installing a dependency only inside one running notebook and assuming other users now have it.
- Adding experiment-only packages to the shared image without a reason.

## 5. Put the right settings in the right file

### Goal of this section

Avoid mixing notebook-local settings, JupyterHub environment forwarding, and Spark cluster defaults.

### What you will create or change

- `docker-compose.yml` when you add new environment variables to the JupyterHub service
- `jupyterhub/jupyterhub_config.py` when you forward variables to user servers
- `spark/conf/spark-defaults.conf` when you change Spark-wide engine behavior

### Exact steps

Use this rule set:

| Setting type | Put it here | Example |
|---|---|---|
| service endpoint or credential that every notebook should see | `docker-compose.yml` and `jupyterhub/jupyterhub_config.py` | `MLFLOW_TRACKING_URI`, `TRINO_HOST` |
| Spark engine behavior shared by all users | `spark/conf/spark-defaults.conf` | Iceberg catalog settings, S3 endpoint, serializer |
| one notebook's temporary choice | the notebook itself | a one-off filter, one chart, a sample limit |

If you add a new forwarded environment variable:

1. add it under the `jupyterhub` service in `docker-compose.yml`
2. add it to `c.Spawner.environment` in `jupyterhub/jupyterhub_config.py`
3. rebuild or restart JupyterHub
4. verify the variable appears in a new user terminal

### What CI/CD or the platform does next

When the change is committed, CI/CD rebuilds or restarts JupyterHub so future user servers inherit the new settings.

### How to verify

Healthy looks like:

- the variable exists in a new JupyterHub terminal
- the notebook reads it with `os.environ[...]`

Broken looks like:

- the variable exists in Compose but not inside the notebook
- the variable exists in the notebook only because you manually exported it in one terminal

### Common mistakes

- Editing only `docker-compose.yml` and forgetting `jupyterhub/jupyterhub_config.py`.
- Putting Spark catalog configuration into a notebook cell instead of `spark-defaults.conf`.

## 6. Use JupyterHub responsibly

### Goal of this section

Keep the shared environment usable for other people and keep your work reproducible.

### What you will create or change

- your working habits, not a code file

### Exact steps

Follow these rules:

1. Shut down notebooks you are not using.
2. Do not keep large DataFrames in memory if you only need a sample.
3. Use Spark for distributed work and pandas only for small inspection output.
4. Delete scratch notebooks when you are done or move the real logic into repository files.
5. Never store passwords inside notebook cells.
6. Never treat the notebook home directory as your only copy of production logic.

### What CI/CD or the platform does next

Nothing. This is operating discipline, not an automated deployment step.

### How to verify

Healthy looks like:

- your server starts quickly
- Spark jobs complete and disappear from the active app list
- your repository contains the permanent code

Broken looks like:

- your server becomes slow because old notebooks are still running
- Spark shows long-running idle applications
- the only copy of important code is inside a notebook

### Common mistakes

- Leaving a heavy notebook kernel running overnight.
- Building a working experiment in JupyterHub and never moving it into Git.
