# Practice Lab 2

## Simpler Repository-Native Workflow

This guide teaches the easier operational path.

In this lab, the learner is allowed to make changes directly inside this `ml-platform` repository. That is the main simplification. The workflow is still disciplined:

- no `docker exec`
- no direct live-container editing
- no real-time container manipulation as a substitute for code changes
- changes still move through Git, commit history, CI/CD, and deployment

Before starting, read [PRACTICE_LAB_FOUNDATIONS.md](./PRACTICE_LAB_FOUNDATIONS.md).

## 1. Goal of Lab 2

The goal is to help a beginner learn the platform end to end without first managing multiple repositories.

Instead of splitting work across many repos, the learner works in the already-structured areas of this repository:

- dbt models in `dbt/retail/`
- Feast definitions in `feast/project/`
- quality logic in `great_expectations/` and `quality/`
- notebooks in `notebooks/`
- orchestration references in `airflow/dags/`
- supporting platform logic in other repo-owned paths when the exercise requires it

This makes the workflow simpler to operate, but it does not remove engineering discipline.

## 2. The key rule of Lab 2

The repository is writable. The running containers are not.

That means:

- you change files in Git
- you commit and push those files
- CI validates them
- deployment updates the running services

You do not:

- open a container and patch files interactively
- use `docker exec` as a shortcut
- make a fix that only exists in runtime state

## 3. What the student is allowed to change

Lab 2 gives the learner a larger change surface than Lab 1.

### 3.1 Typical allowed changes

- dbt models, tests, and documentation
- Feast feature definitions
- learner notebooks and notebook-supporting code
- Great Expectations suites or quality-generation logic
- training logic and model-related support files when the exercise requires it
- selected Airflow, bootstrap, or related repository logic when the exercise is specifically about that workflow

### 3.2 Areas that should still be treated carefully

- `docker-compose.yml`
- service Dockerfiles
- platform-wide environment wiring
- authentication settings
- shared service configuration

A beginner can inspect these files, but should not treat them as the normal place for application-level changes unless the exercise explicitly says to do so.

## 4. Repo map for Lab 2

Use this map to understand where common types of work happen.

| Task | Primary path in this repo | Why it lives there |
|---|---|---|
| inspect or change transformations | `dbt/retail/models/` | dbt is the transformation layer |
| inspect dbt tests and docs | `dbt/retail/models/*.yml` and generated docs under `dbt/retail/target/` | dbt documents and validates models |
| inspect or change feature definitions | `feast/project/features.py` | Feast feature views live here |
| inspect feature store config | `feast/project/feature_store.yaml` | Feast registry and store wiring |
| inspect or change quality generation | `quality/generate_quality_assets.py` | builds Great Expectations and Evidently outputs |
| inspect or change orchestration | `airflow/dags/retail_pipeline.py` | Airflow DAG definition |
| inspect learner workflows | `notebooks/` | guided learning scripts |
| inspect user environment config | `jupyterhub/jupyterhub_config.py` | notebook session defaults and limits |
| inspect shared Spark config | `spark/conf/spark-defaults.conf` | cluster-wide Spark settings |
| inspect model serving bundle | `mlserver/models/churn-model/` | MLServer loads the model from here |

## 5. The Lab 2 workflow from start to finish

This is the full beginner-friendly flow.

### 5.1 Step 1: understand the current platform state

Open the main UIs and get oriented before editing any code.

Use:

- CloudBeaver to inspect the raw PostgreSQL source
- Trino to inspect lakehouse tables
- dbt docs to see transformation lineage
- Feast UI to see the registered features
- MLflow to see the existing demo runs
- Airflow to see the pipeline stages
- Great Expectations docs and Evidently reports to see quality outputs
- MinIO Console to inspect stored artifacts
- Grafana and Prometheus to see operational monitoring
- JupyterHub for notebook-based exploration

This step matters because beginners need to know what "normal" looks like before they change anything.

### 5.2 Step 2: decide what kind of change you are making

Ask the question in plain language:

- am I changing raw-to-analytics SQL?
- am I changing reusable features?
- am I changing training or evaluation logic?
- am I changing data validation?
- am I changing the pipeline sequence?

That question tells you which folder to edit.

### 5.3 Step 3: create a branch and edit the repository

Make your change in the correct directory.

Examples:

- add or adjust a dbt model in `dbt/retail/models/`
- add tests in a `schema.yml` file
- update `feast/project/features.py`
- improve `quality/generate_quality_assets.py`
- update a notebook in `notebooks/`

Even though the repo is local and writable, treat the branch as the unit of work.

### 5.4 Step 4: explain the change in beginner terms

Write down:

- what you changed
- what new output you expect
- which component should reflect the change after deployment

This habit makes debugging easier later.

### 5.5 Step 5: commit and push

This is where Lab 2 remains production-aware.

The intended workflow is:

1. commit the change
2. push the branch
3. let CI/CD run
4. let the deployment process update the correct services

This teaches an important lesson: even in a simpler setup, deployment should be pipeline-driven rather than shell-driven.

### 5.6 Step 6: CI/CD validates the repository change

This repository does not need learners to shell into services. Instead, the expected CI/CD path should do the equivalent validation automatically.

A strong Lab 2 CI pipeline would typically:

- validate Python syntax and tests
- validate dbt parsing and build logic
- validate Feast definitions
- validate Airflow DAG imports
- run quality-generation checks
- build any changed images or artifacts
- publish the updated outputs
- deploy the changed components

The exact CI implementation can vary, but the operating model should stay the same.

### 5.7 Step 7: confirm the deployment result

After CI/CD finishes, inspect the platform through its normal interfaces.

That means:

- no `docker exec`
- no manual file patching in running containers
- use UIs, APIs, logs, and generated artifacts

## 6. A detailed Lab 2 example

This example shows how a beginner would work inside this repository.

### Scenario

You want to add a new customer metric to the transformed dataset and make it visible in the feature store.

### 6.1 Inspect the upstream data

Use CloudBeaver or Trino to inspect:

- `postgresql.public.orders`
- `postgresql.public.customers`
- current analytical tables under `iceberg.analytics`

Why this matters:

- you need to know which source field exists
- you need to know whether the desired signal already appears downstream

### 6.2 Update the dbt layer

Go to `dbt/retail/models/`.

Typical beginner path:

1. inspect staging models under `dbt/retail/models/staging/`
2. inspect marts under `dbt/retail/models/marts/`
3. identify the model that should expose the new metric
4. update the SQL
5. update or add tests and descriptions in the related YAML file

What you are learning:

- dbt is where business-facing SQL logic becomes a maintained asset
- tests and docs are part of the model, not an afterthought

### 6.3 Update the feature store layer

Go to `feast/project/features.py`.

Inspect:

- entity definitions
- file sources
- feature views

Then update the relevant feature view so the new field is exposed in Feast.

What you are learning:

- Feast does not invent features on its own
- it exposes features based on trusted upstream datasets
- the schema in Feast must align with the data written upstream

### 6.4 Update validation if needed

If the new metric introduces a new assumption, update:

- dbt tests
- Great Expectations logic in `quality/generate_quality_assets.py`
- supporting expectation suites if the exercise requires explicit checks

What you are learning:

- every meaningful data change should come with a validation story

### 6.5 Commit and push

Now commit the repository changes.

The intended CI/CD behavior is:

- dbt checks run
- feature definitions validate
- quality logic validates
- artifacts are rebuilt
- the deployment refreshes the affected services

### 6.6 Validate the result after deployment

Use the platform components in this order:

1. Airflow: confirm pipeline success if the change triggers pipeline work
2. dbt docs: confirm lineage and model docs
3. Trino: query the new field from `iceberg.analytics`
4. Feast UI: confirm the feature view reflects the change
5. MinIO: inspect the related offline feature files if necessary
6. Great Expectations: confirm validation still passes
7. MLflow: confirm retraining results if the model was affected
8. MLServer: confirm serving remains healthy if inference changed
9. Evidently: inspect whether the new signal changed monitoring behavior

## 7. How each major component is used in Lab 2

This section explains the platform component coverage specifically for the simpler workflow.

### 7.1 CloudBeaver

Use it to:

- inspect raw PostgreSQL tables
- browse schemas without writing Python code
- sanity-check source data before changing dbt logic

Usually configure:

- little or nothing as a learner

Mostly inspect:

- raw tables and column values

### 7.2 JupyterHub

Use it to:

- explore data safely
- prototype SQL or Python
- understand the workflow with notebooks before turning ideas into committed repo code

Important rule:

- notebook exploration is useful, but committed repository code is the deployable truth

Mostly configure:

- environment defaults only when the lab specifically covers environment management

Mostly inspect or use:

- Spark access
- Trino access
- MLflow access
- package availability

### 7.3 Spark

Use it to:

- understand distributed processing and custom ETL
- inspect or prototype larger transformations

Mostly configure:

- shared defaults in `spark/conf/spark-defaults.conf`

Mostly inspect:

- job behavior in the Spark UI
- worker availability and resource use

### 7.4 Spark workers

Inspect:

- whether the worker is alive
- memory and core allocation
- whether jobs are overloaded

This teaches that distributed compute has capacity limits and is not magic.

### 7.5 Trino

Use it to:

- query `iceberg.retail_raw`
- query `iceberg.analytics`
- query PostgreSQL sources through the `postgresql` catalog

Inspect:

- schema presence
- result correctness
- whether a transformation change appears where expected

### 7.6 MinIO

Use it to inspect:

- lakehouse and feature files
- MLflow artifacts
- other generated objects

This is how you learn that a modern platform depends heavily on object storage, not just databases.

### 7.7 Airflow

Use it to:

- inspect the pipeline order
- trigger or observe scheduled work
- confirm whether updated logic ran successfully

Inspect:

- task graph
- logs
- task duration
- retries

### 7.8 Superset

Use it to:

- inspect analytical outputs through a BI interface
- confirm that transformed data is usable by business-facing tools

Mostly inspect:

- whether the new dimensions or metrics remain understandable

### 7.9 Grafana

Use it to:

- watch platform health while pipelines run
- notice if resource issues or service instability coincide with your change

### 7.10 Prometheus

Use it to:

- query raw metrics when a Grafana dashboard suggests a problem

This helps learners understand the difference between a dashboard and the metric source behind it.

### 7.11 Great Expectations

Use it to:

- inspect dataset validation output
- learn what assumptions the platform is actively checking

Configure when:

- you add a new important quality rule

Inspect when:

- a new field or metric should satisfy a constraint

### 7.12 Evidently

Use it to:

- inspect drift or monitoring reports
- understand what happens after training and scoring

Mostly inspect:

- feature changes
- drift indicators
- data-quality summary sections

### 7.13 Feast

Use it to:

- inspect entities and feature views
- verify that new features are registered and usable

Configure when:

- you change `features.py` or `feature_store.yaml`

Inspect when:

- you need to confirm the platform can serve the feature consistently

### 7.14 MLflow

Use it to:

- inspect runs, metrics, and artifacts
- compare model behavior after a training-related change

Configure when:

- the exercise is about experiment tracking or training logic

Inspect when:

- you want to confirm the model output actually changed

### 7.15 MLServer

Use it to:

- confirm the serving endpoint is healthy
- understand how a model becomes an inference service

Inspect:

- readiness
- whether the expected bundle is present

### 7.16 dbt docs

Use it to:

- inspect lineage
- confirm descriptions
- confirm tests and dependencies

This is the simplest way for a beginner to understand how dbt models connect together.

## 8. How to work responsibly inside this repo

Lab 2 is simpler, but not casual.

### 8.1 Good habits

- make the smallest change that proves the concept
- update docs and tests with the change
- verify through supported UIs after deployment
- keep notebooks exploratory and repository code authoritative

### 8.2 Bad habits

- editing a running container to "just fix it quickly"
- changing many unrelated directories in one branch
- making dbt or feature changes without updating tests or docs
- using notebooks as the only place where important logic exists

## 9. Beginner debugging flow for Lab 2

Use this order when a change does not behave as expected.

1. Check Airflow to see whether the workflow ran.
2. Check dbt docs and Trino to confirm the transformed data changed.
3. Check Great Expectations if a data-quality gate may be blocking progress.
4. Check Feast if the issue is feature exposure.
5. Check MLflow if the issue is training output.
6. Check MLServer if the issue is serving.
7. Check MinIO if artifacts or parquet outputs may be missing.
8. Check Grafana and Prometheus if the platform itself looks unhealthy.

This sequence is much more reliable than trying to inspect a live container by shelling into it.

## 10. End condition for Lab 2

You have completed Lab 2 successfully when you can:

- identify the correct directory for a change in this repository
- explain how that change should move through commit, push, CI/CD, and deployment
- validate the result through platform UIs instead of direct container access
- explain what each major platform component does in the learning workflow

If you can do that, you have learned the simpler but still production-aware operating model.
