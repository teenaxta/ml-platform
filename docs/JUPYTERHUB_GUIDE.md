# JupyterHub Environment Guide

This document focuses on JupyterHub as a user environment, not as a place to hardcode one fixed database target.

The main purpose is to explain:

- how user environments are configured
- how Spark-related settings should be managed
- how packages should be managed
- how resource usage should be controlled
- how users should work safely and predictably inside their notebook environments

## 1. What JupyterHub is doing in this platform

JupyterHub provides a managed notebook workspace for users who need to:

- inspect data
- prototype transformations
- test ML ideas
- connect to Spark, Trino, MLflow, and source systems

It is a workspace layer, not the source of truth for production deployment.

That means:

- exploration can happen in JupyterHub
- reusable platform logic should move into the repository
- deployment should happen through Git and CI/CD

## 2. The configuration layers

The cleanest way to understand JupyterHub in this repo is to separate configuration by scope.

### 2.1 `docker-compose.yml`

This is where shared service endpoints, credentials, and platform defaults enter the `jupyterhub` service.

Examples:

- `SPARK_MASTER`
- `TRINO_HOST`
- `MLFLOW_TRACKING_URI`
- `DEMO_POSTGRES_HOST`
- `AWS_S3_ENDPOINT`

Use this layer when:

- the value belongs to the environment as a whole
- every user session should inherit it

### 2.2 `jupyterhub/jupyterhub_config.py`

This is where JupyterHub forwards environment values into each user server and applies resource rules.

Examples already present in this repo:

- `c.Spawner.environment`
- `c.Spawner.mem_limit = "4G"`
- `c.Spawner.cpu_limit = 2.0`
- idle culler configuration

Use this layer when:

- the value should be available to every user session
- you want to control notebook server limits or behavior

### 2.3 `spark/conf/spark-defaults.conf`

This is where cluster-wide Spark defaults belong.

Use this layer when:

- the setting should apply to all Spark jobs
- the setting describes shared Spark behavior rather than one notebook choice

Examples:

- catalog wiring
- S3 or MinIO endpoint defaults
- serializer settings
- SQL extensions
- shuffle defaults

### 2.4 `jupyterhub/Dockerfile`

This is where shared packages for all users should be installed.

Use this layer when:

- everyone should have the same Python package
- the package is part of the supported notebook environment

### 2.5 Notebook code

Notebook code should read from environment variables and use platform defaults instead of hardcoding service addresses.

Good example:

```python
import os

trino_host = os.environ["TRINO_HOST"]
spark_master = os.environ["SPARK_MASTER"]
mlflow_uri = os.environ["MLFLOW_TRACKING_URI"]
```

Bad example:

```python
trino_host = "trino"
spark_master = "spark://spark-master:7077"
mlflow_uri = "http://mlflow:5000"
```

The second style makes notebooks less portable and harder to maintain.

## 3. What is already centralized in this repo

The current JupyterHub setup already forwards these kinds of values into user sessions:

- Spark master endpoint
- Trino host, port, catalog, and schema
- MLflow tracking URI and credentials
- Iceberg JDBC connection values
- demo PostgreSQL connection values
- AWS and MinIO-related values
- Java and PySpark defaults

That means the notebooks can focus on analysis logic instead of repeating platform wiring.

## 4. Spark-related environment configuration

Spark deserves its own section because beginners often mix cluster settings with notebook settings.

### 4.1 What belongs in shared Spark configuration

Put these in `spark/conf/spark-defaults.conf` when they should apply to all users and jobs:

- Iceberg catalog configuration
- S3 or MinIO integration
- Spark SQL extensions
- cluster-wide serialization defaults
- cluster-wide partitioning defaults

These are platform-level decisions.

### 4.2 What belongs in JupyterHub environment variables

Put these in JupyterHub environment wiring when notebooks should read them directly:

- source database host, database name, and credentials
- Trino host and default catalog
- MLflow tracking URI
- endpoints that depend on the environment

These are connection values, not Spark engine behavior.

### 4.3 What belongs in notebook-level choices

Keep these in notebook code only when they are truly part of one analysis:

- temporary dataframe variables
- one-off exploratory queries
- experiment-specific feature subsets
- temporary plotting settings

Do not promote one-off experiment values into platform-wide configuration unless they are genuinely shared needs.

### 4.4 How to work with Spark responsibly

When using Spark in JupyterHub:

- avoid collecting large datasets to the notebook process unless necessary
- inspect only the first rows when learning the shape
- use Spark for distributed work and pandas for small local inspection
- watch the Spark UI to understand what your notebook started

### 4.5 How to inspect Spark workers

Open the Spark master and worker UIs.

Check:

- whether the worker is alive
- how much memory is assigned
- how many cores are available
- whether a job is waiting or running

If Spark feels "slow," inspect the worker UI before changing code blindly.

## 5. Flexible environment configuration patterns

This guide intentionally avoids hardcoding a single target database because notebook environments should stay flexible.

### 5.1 Preferred pattern

Use environment variables or small user-config objects to decide which target to use.

For example, notebook code can read:

- `TRINO_CATALOG`
- `TRINO_SCHEMA`
- `DEMO_POSTGRES_HOST`

This keeps the environment portable across local, shared, and hosted variants.

### 5.2 Avoid these patterns

- hardcoding hostnames directly in notebook cells
- storing passwords in notebook files
- assuming one schema or catalog will always be correct forever
- changing platform-wide config just for one short-lived experiment

## 6. Package and environment management

Package management should be predictable.

### 6.1 If every user needs a package

Add it to `jupyterhub/Dockerfile` and rebuild the image.

Why:

- every user gets the same environment
- notebooks stay reproducible
- package installation does not depend on a manual step

### 6.2 If one user needs a temporary experiment package

Treat that as exploratory work only.

Prefer one of these paths:

- add the package properly to the image if it is becoming standard
- use a clearly temporary, user-local environment if the package is purely experimental

Do not let long-lived important workflows depend on "I installed it once in a notebook terminal."

### 6.3 Why ad hoc package installs are risky

- they are hard to reproduce
- other users do not have the same environment
- they disappear when the environment is rebuilt
- debugging becomes much harder

## 7. Resource and usage management

JupyterHub is a shared user environment. That means resource discipline matters.

### 7.1 Current repo limits

The current config sets:

- memory limit: `4G`
- CPU limit: `2.0`
- idle culler timeout: 1 hour

These limits teach an important habit: a notebook environment is not infinite compute.

### 7.2 Good usage patterns

- stop or idle out sessions you are not using
- use Spark for larger work rather than forcing everything into pandas
- avoid reading full large tables into memory without filtering
- save durable logic back into repository files

### 7.3 Bad usage patterns

- leaving heavy sessions open all day
- repeatedly loading large datasets into local notebook memory
- treating one notebook server as a long-running production service
- hiding important logic only in notebook cells

## 8. How users should work inside their JupyterHub environments

This is the recommended operating model.

### 8.1 Use JupyterHub for exploration

Good uses:

- inspect data shape
- test Spark connectivity
- try Trino queries
- compare model ideas
- understand how the platform works

### 8.2 Move durable logic back into the repository

When notebook work becomes important, convert it into maintained code:

- dbt models
- Python modules
- Airflow task logic
- Feast definitions
- quality checks

This is how exploratory work becomes platform work.

### 8.3 Keep secrets out of notebooks

Use environment variables passed by JupyterHub.

Do not:

- paste passwords into notebook cells
- commit credentials
- duplicate connection strings in many notebooks

### 8.4 Prefer `.py` walkthroughs when appropriate

This repository already uses `.py` notebook-style walkthroughs in `notebooks/`.

Why that is reasonable:

- cleaner Git diffs
- easier code review
- less notebook metadata noise

Use `.ipynb` when rich interactive output is essential. Use `.py` when the goal is versioned, reviewable teaching material.

## 9. How to update JupyterHub defaults safely

When a shared notebook default needs to change:

1. update `docker-compose.yml` if the value enters the JupyterHub service there
2. update `jupyterhub/jupyterhub_config.py` if the spawned user servers need that value
3. update notebooks to read the variable instead of using a literal value
4. rebuild or restart JupyterHub as needed

Typical commands:

```bash
docker compose build jupyterhub
docker compose up -d jupyterhub
```

If only compose or JupyterHub config changed, a restart may be enough.

## 10. How to connect external tools such as VS Code

VS Code can connect to the Jupyter server started by JupyterHub.

High-level process:

1. log into JupyterHub
2. start your server
3. run `jupyter server list` in a terminal inside JupyterLab
4. copy the single-user server URL
5. point VS Code's Jupyter extension at that existing server

This lets you keep the environment managed by JupyterHub while using VS Code as a client.

## 11. Troubleshooting checklist

### 11.1 Notebook cannot reach Spark

Check:

- `SPARK_MASTER`
- Spark master UI health
- worker availability
- whether the cluster is already overloaded

### 11.2 Notebook cannot reach Trino

Check:

- `TRINO_HOST`
- `TRINO_PORT`
- Trino service health
- whether the chosen catalog and schema exist

### 11.3 Notebook cannot log to MLflow

Check:

- `MLFLOW_TRACKING_URI`
- credentials
- MLflow service availability

### 11.4 Notebook package is missing

Check:

- whether the package belongs in `jupyterhub/Dockerfile`
- whether the image was rebuilt
- whether the user is depending on an untracked manual install

### 11.5 Notebook is slow or crashes

Check:

- memory pressure
- pandas usage on large datasets
- whether the work should be pushed to Spark
- whether the session needs restart

## 12. End condition for this guide

You understand this guide when you can explain:

- which settings belong in Compose, JupyterHub config, Spark defaults, image build files, and notebooks
- how to keep notebook environments flexible without hardcoding one target database
- how to manage packages reproducibly
- how to work within shared resource limits
- how to use JupyterHub for exploration without turning it into an uncontrolled deployment path
