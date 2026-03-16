# Practice Lab Foundations

This document teaches the shared ideas, setup steps, and platform rules that apply to both practice labs.

The target reader knows some Python but is new to platform engineering, MLOps, registries, CI/CD, feature stores, and infrastructure workflows. Because of that, this guide explains each concept before it relies on it.

## 1. What this platform is

This repository represents a teaching version of a modern data and machine learning platform. It takes one business storyline, retail analytics and customer churn prediction, and shows how the same data moves through the full lifecycle:

1. raw business data starts in an operational PostgreSQL database
2. Spark and Trino move that data into a lakehouse layout
3. dbt turns raw tables into analytics-ready models
4. Great Expectations validates the data
5. Feast publishes reusable features for training and serving
6. MLflow tracks experiments and model outputs
7. MLServer serves a trained model
8. Evidently produces monitoring reports
9. Airflow orchestrates the end-to-end workflow
10. Superset, CloudBeaver, Grafana, and Prometheus help people inspect or observe the system
11. JupyterHub gives users a safe place to explore and prototype

The goal of the labs is not only to "make the stack run." The goal is to teach where each part fits and how changes move safely from code to a deployed platform.

## 2. Architecture overview

Think of the platform as four layers.

### 2.1 Source and storage layer

- `demo-postgres` is the operational source system
- `MinIO` is the object store
- `Iceberg REST` is the table catalog

This layer holds the original data and the lakehouse storage metadata.

### 2.2 Compute and transformation layer

- `Spark` provides distributed compute for custom ETL, exploration, and model preparation
- `Trino` is the shared SQL query engine and powers the seeded ingestion and transformation flow in this teaching stack
- `dbt` manages versioned SQL transformations

This layer turns raw data into trusted analytical tables.

### 2.3 Feature, training, and serving layer

- `Feast` defines and serves reusable features
- `MLflow` tracks experiments, runs, models, and artifacts
- `MLServer` exposes a trained model as an inference endpoint

This layer is where analytics turns into machine learning assets.

### 2.4 Orchestration, quality, and observability layer

- `Airflow` schedules and coordinates tasks
- `Great Expectations` validates datasets
- `Evidently` generates monitoring and drift reports
- `Superset` provides dashboards and BI exploration
- `CloudBeaver` provides ad hoc database inspection
- `Grafana` and `Prometheus` provide operational monitoring
- `JupyterHub` provides user workspaces
- the `dbt docs` site acts as the dbt dashboard for lineage, model docs, and tests

This layer helps people run, inspect, understand, and trust the system.

## 3. Where the platform files live in this repository

These paths matter in both labs because they show how the current teaching stack is organized:

| Area | Path in this repo | What it contains |
|---|---|---|
| Platform startup | `docker-compose.yml` | all services, dependencies, and environment wiring |
| Airflow workflow | `airflow/dags/retail_pipeline.py` | orchestration entry point |
| Bootstrap logic | `bootstrap/seed_demo.py` | ingestion, feature publishing, training, and artifact refresh flow |
| dbt project | `dbt/retail/` | SQL models, tests, docs metadata |
| dbt connection profile | `dbt/profiles.yml` | Trino connection used by dbt |
| Feast project | `feast/project/` | feature store config and feature definitions |
| JupyterHub config | `jupyterhub/jupyterhub_config.py` | notebook environment defaults and limits |
| Spark defaults | `spark/conf/spark-defaults.conf` | cluster-wide Spark settings |
| Quality generation | `quality/generate_quality_assets.py` | Great Expectations and Evidently artifacts |
| Model serving bundle | `mlserver/models/churn-model/` | deployed model files used by MLServer |
| Learner notebooks | `notebooks/` | guided exploration and training scripts |

In Lab 1 these paths act mainly as a reference implementation. In Lab 2 they are part of the actual learner workflow.

## 4. Common setup steps for both labs

These are the baseline setup steps for running the teaching stack locally.

### 4.1 Prepare environment variables

Copy the sample environment file:

```bash
cp .env.example .env
```

Then update the passwords and secrets. At minimum, generate fresh values for:

- `AIRFLOW_FERNET_KEY`
- `MLFLOW_FLASK_SECRET_KEY`
- `SUPERSET_SECRET_KEY`

### 4.2 Build the platform images

```bash
docker compose build
```

This builds the custom images for services such as Airflow, JupyterHub, dbt, Feast, MLflow, MLServer, Superset, and the bootstrap jobs.

### 4.3 Start the platform

```bash
docker compose up -d
docker compose logs -f --tail=50 raw-bootstrap dbt-bootstrap platform-bootstrap feast-bootstrap quality-bootstrap
```

Wait for the one-shot bootstrap services to complete successfully. They seed the learning environment by:

- loading source tables into Iceberg-backed storage
- running dbt models and tests through Trino
- generating the dbt docs site
- publishing Feast feature files
- training a sample churn model
- logging an MLflow run
- preparing an MLServer model bundle
- generating Great Expectations Data Docs
- generating an Evidently report

### 4.4 Open the platform UIs

See [ACCESS_AND_URLS.md](./ACCESS_AND_URLS.md) for the full list. The key entry points are:

- JupyterHub
- Airflow
- Superset
- MLflow
- Grafana
- Prometheus
- MinIO Console
- Feast UI
- dbt docs
- Great Expectations docs
- Evidently report
- Spark master and worker UIs
- CloudBeaver

## 5. Core ideas you need before starting the labs

This section explains the shared terms that often confuse beginners.

### 5.1 What a repository is

A repository, usually called a "repo," is the version-controlled home for code and configuration. It stores files, Git history, branches, pull requests, and reviews.

Why repositories matter:

- they preserve change history
- they let teams review code before merge
- they are the usual trigger point for CI/CD
- they make rollback possible

In a simple setup one repo can contain everything. In a larger setup different concerns may be separated into multiple repos.

### 5.2 What CI/CD is

`CI` means continuous integration. It answers: "When someone pushes code, how do we automatically validate that change?"

Typical CI checks include:

- unit tests
- SQL or Python linting
- dbt parsing and tests
- image builds
- package builds
- security scans

`CD` means continuous delivery or continuous deployment. It answers: "Once the code is validated, how does it move into a runtime environment?"

Typical CD steps include:

- publishing an image or package
- promoting a version to staging or production
- updating a deployment manifest
- triggering a rollout

In both labs, the important rule is the same: runtime environments should change because reviewed code was merged and a pipeline deployed it, not because someone manually edited a live container.

### 5.3 What a container is

A container is a packaged runtime environment. It includes:

- application code
- operating-system level dependencies
- libraries
- a default command to run

You can think of it as a sealed delivery unit for software.

Why containers are used:

- they reduce "works on my machine" problems
- they make deployments more repeatable
- they provide clear packaging boundaries

### 5.4 What an image is

An image is the build artifact used to create containers.

Important distinction:

- image: the packaged blueprint
- container: a running instance of that blueprint

When a CI pipeline builds a Docker image, it is producing a versioned artifact that can later be run in Airflow, Kubernetes, Docker Compose, or another platform.

### 5.5 What a tag is

A tag is the version label attached to an image.

Examples:

- `ghcr.io/acme/analytics-dbt:main-4f92c2a`
- `ghcr.io/acme/ml-training:release-2026-03-16`
- `ghcr.io/acme/feature-store:1.4.0`

Why tags matter:

- they tell you exactly which version is being deployed
- they support reproducibility
- they make rollback possible

Good practice is to use immutable tags such as commit SHA values, then optionally map human-friendly release tags on top.

### 5.6 What a container registry is

A container registry stores built images so other systems can pull them later.

Why registries exist:

- CI builds images once
- deployment systems pull the exact approved image
- teams avoid copying source files directly into running systems

Common registries:

- GitHub Container Registry: `ghcr.io`
- Amazon Elastic Container Registry: `*.dkr.ecr.*.amazonaws.com`
- Google Artifact Registry
- Azure Container Registry
- self-hosted Harbor or Artifactory

How a registry workflow usually works:

1. CI checks out the repository
2. CI builds an image from a `Dockerfile`
3. CI authenticates to the registry
4. CI pushes the image with one or more tags
5. deployment tooling references the published tag

Example with GitHub Container Registry:

1. create or choose a GitHub organization or repository
2. enable GitHub Actions for the repo
3. store credentials or use the built-in `GITHUB_TOKEN`
4. add a workflow that logs in to `ghcr.io`
5. build the image
6. push a tag such as `ghcr.io/<org>/<image-name>:<git-sha>`
7. reference that tag from Airflow, Kubernetes, or another deployment layer

What beginners often miss is that "publishing" does not mean copying code into a container by hand. It means producing a versioned artifact and placing it in a registry so the runtime can pull it predictably.

### 5.7 What an artifact is

An artifact is any versioned output created by a build or pipeline step.

Examples in this platform:

- a container image
- a trained model file
- a Great Expectations Data Docs site
- an Evidently HTML report
- dbt documentation output
- a parquet dataset in MinIO

Artifacts matter because they are the concrete outputs that later stages depend on.

### 5.8 What deployment means

Deployment is the controlled process of making a new artifact active in an environment.

Examples:

- Airflow starts using a new training image tag
- MLServer serves a new model bundle
- Superset points at a refreshed dataset
- a new dbt image is pulled into a job runner

Deployment is not the same as editing files locally. Deployment means the runtime environment receives and activates a versioned output.

### 5.9 What dbt is

dbt is a framework for turning SQL transformations into versioned, testable, documented data assets.

dbt gives you:

- SQL models
- dependency tracking with `ref()`
- tests
- documentation
- lineage graphs

Where dbt fits in this architecture:

- Trino is the SQL execution engine
- dbt is the transformation framework that tells Trino what to build
- dbt outputs trusted analytics tables such as `customer_360` and `churn_training_dataset`

What the dbt dashboard means in this stack:

- the dbt docs site at `http://localhost:8090`
- model lineage
- descriptions
- test status
- schema relationships

### 5.10 What a feature store is

A feature store manages reusable, well-defined model features so that training and serving use the same definitions.

Why feature stores exist:

- feature logic should not be reinvented separately in each notebook or service
- training and inference should agree on feature meaning
- feature freshness and lineage should be visible

### 5.11 What Feast is

Feast is the feature store used in this platform.

Where Feast fits:

- dbt and Spark prepare data
- feature definitions in `feast/project/features.py` describe how features are exposed
- feature data is stored offline in MinIO-backed parquet files
- selected data is materialized into an online store for low-latency access

What Feast is not:

- it is not the raw data warehouse
- it is not the training framework
- it is not the serving endpoint itself

It is the layer that standardizes feature definitions and makes them reusable.

### 5.12 What MLflow is

MLflow is the experiment tracking and model lifecycle tool.

It stores:

- run metadata
- metrics
- parameters
- model artifacts
- model versions

Why it matters:

- you can compare experiments instead of losing notebook results
- you can track which data and code produced a model
- you have a record of what was trained and promoted

### 5.13 What MLServer is

MLServer is the runtime that serves a trained model as an API.

Why it matters:

- training a model is not enough
- a downstream application needs a predictable endpoint
- serving lets you test the last step of the lifecycle

In this repo, MLServer serves the `churn-model` bundle written into `mlserver/models/churn-model/`.

### 5.14 What Great Expectations is

Great Expectations is a data validation framework.

It lets teams define expectations such as:

- a column must not be null
- values must stay within a range
- labels must come from an allowed set

Why it matters:

- broken or surprising data can silently poison analytics and ML work
- validation makes assumptions explicit

### 5.15 What Evidently is

Evidently creates data and model monitoring reports.

Why it matters:

- production data can drift away from training data
- model inputs can change in subtle ways
- teams need a readable report showing whether distributions shifted

### 5.16 What observability means

Observability is the ability to understand system behavior from outputs such as metrics, logs, dashboards, traces, and health signals.

In this stack:

- Prometheus collects metrics
- Grafana visualizes metrics
- Airflow shows run status
- Spark UIs show distributed job activity
- MLflow shows experiment outcomes
- Great Expectations and Evidently show data and model quality outputs

### 5.17 Why `docker exec` is not allowed in these labs

This rule exists for engineering reasons, not for artificial difficulty.

When people use `docker exec` to change a running container:

- the change is not version-controlled
- the change is easy to forget
- the change disappears when the container is recreated
- nobody can review it properly
- CI/CD did not validate it

That is why both labs prohibit `docker exec` as part of the intended workflow.

If a change matters, it should be:

1. written in code or configuration
2. committed to Git
3. validated by CI
4. deployed through the normal release path

## 6. Shared platform component map

Both labs use the same components. The difference is how much the learner is allowed to change directly in the repository layout.

| Component | What it is | Why it exists | Typical learner action |
|---|---|---|---|
| CloudBeaver | browser SQL client | inspect schemas and query databases manually | browse source tables and verify results |
| JupyterHub | managed notebook workspace | exploration and controlled experimentation | run notebooks and inspect data safely |
| Spark | distributed processing engine | large transforms, custom ETL, and notebook-driven distributed work | observe jobs and run notebook-driven Spark exploration |
| Spark worker UI | worker status page | inspect resources and task activity | confirm worker health and load |
| Trino | SQL query engine | one SQL layer over Iceberg and PostgreSQL | query raw and transformed data |
| MinIO | object store | store lakehouse files, features, artifacts | inspect parquet files, model artifacts, and generated outputs |
| Airflow | orchestrator | scheduled, visible execution of pipelines | trigger or observe DAG runs |
| Superset | BI tool | dashboards and SQL exploration | inspect analytics outputs visually |
| Grafana | monitoring UI | display platform metrics | inspect service health trends |
| Prometheus | metrics collector | collect runtime metrics | query metrics when debugging |
| Great Expectations | data quality framework | validate important datasets | inspect Data Docs and check failures |
| Evidently | drift and monitoring reports | inspect data or model drift | open the generated report |
| Feast | feature store | manage reusable features | inspect features, definitions, and materialization state |
| MLflow | experiment tracker | track runs, metrics, and models | inspect runs and compare models |
| MLServer | model serving runtime | expose model inference endpoint | test serving behavior |
| dbt docs | dbt dashboard | inspect lineage, descriptions, and tests | verify transformed datasets and dependencies |

## 7. What "configure" versus "use" versus "observe" means

This distinction matters in both labs.

### 7.1 Configure

Configuration means defining how a component should behave.

Examples:

- changing `jupyterhub/jupyterhub_config.py`
- changing `spark/conf/spark-defaults.conf`
- changing `feast/project/feature_store.yaml`
- changing service environment variables

### 7.2 Use

Usage means running normal work through the supported interface.

Examples:

- running a notebook in JupyterHub
- querying Trino
- reviewing dbt docs
- triggering an Airflow DAG
- opening MLflow runs

### 7.3 Observe

Observation means checking status, health, artifacts, or outputs without changing the system design.

Examples:

- checking Spark worker memory in the Spark UI
- reading Prometheus metrics
- browsing MinIO objects
- opening an Evidently report
- viewing a Great Expectations Data Docs page

Beginners often mix these actions together. The labs intentionally separate them.

## 8. Shared validation checklist

Use this checklist in both labs after a change is deployed.

### 8.1 Data path validation

- confirm source data exists in `demo-postgres`
- confirm raw tables exist in Trino under `iceberg.retail_raw`
- confirm transformed tables exist in `iceberg.analytics`
- confirm dbt docs show the updated model lineage

### 8.2 Feature and model validation

- confirm Feast sees the expected feature views
- confirm feature files appear in MinIO
- confirm MLflow recorded the expected run
- confirm MLServer is serving the intended model bundle

### 8.3 Quality and monitoring validation

- confirm Great Expectations Data Docs were refreshed
- confirm Evidently report generation succeeded
- confirm Airflow DAG succeeded
- confirm Grafana and Prometheus show the platform is healthy

## 9. Shared debugging habits

When something fails, debug from the outside in.

1. Check the user-facing symptom first.
2. Check the orchestration layer next.
3. Check the execution engine after that.
4. Check storage and artifacts last.

Examples:

- if a table is missing, start with Airflow and dbt docs before blaming Spark
- if a model is missing, check MLflow and bootstrap outputs before checking MLServer
- if a feature lookup looks wrong, check the parquet files in MinIO and the Feast registry before changing training code

This is safer than opening a live container and editing files interactively.

## 10. How the two labs differ

### 10.1 Lab 1

Lab 1 teaches the production operating model:

- infrastructure code is protected
- learners do not write directly in the infrastructure repository
- teams publish artifacts and promote deployments through CI/CD
- repository ownership and deployment boundaries are part of the lesson

### 10.2 Lab 2

Lab 2 teaches the simpler operational model:

- the learner works inside this `ml-platform` repository
- the platform is still treated as code
- changes still move through Git, CI/CD, and deployment
- `docker exec` is still disallowed

Now continue with one of the lab-specific guides.
