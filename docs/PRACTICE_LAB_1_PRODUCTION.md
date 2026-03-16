# Practice Lab 1

## Advanced Production-Style Workflow

This guide teaches the production-grade version of the lab.

The learner is expected to understand the full workflow, but not to make changes directly inside the infrastructure repository. In other words, you are learning how a real team usually works when platform boundaries, review rules, and deployment discipline matter.

Before starting, read [PRACTICE_LAB_FOUNDATIONS.md](./PRACTICE_LAB_FOUNDATIONS.md).

## 1. Goal of Lab 1

The goal is to teach how a data or ML change moves safely from idea to deployed platform output without direct live-container editing and without writing application logic directly inside the infrastructure repository.

This means:

- no `docker exec`
- no ad hoc editing inside running services
- no direct writing in the infrastructure repository for normal learner work
- all important changes flow through repositories, pull requests, CI checks, published artifacts, and controlled deployments

## 2. Production assumptions

This repository is a teaching stack, not a full enterprise platform. For Lab 1, use it as a reference implementation of the platform itself.

The realistic production assumption is:

- the platform repository defines the shared runtime and platform services
- learner-facing changes live in separate delivery repositories, or in a tightly managed monorepo that is still separate from platform infrastructure ownership

That lets teams protect the platform while still allowing analysts, data engineers, and ML engineers to deliver changes safely.

## 3. Operating rules

These rules are part of the lab.

### 3.1 What you may do

- write code in the correct delivery repository
- open pull requests
- let CI validate the change
- publish images, packages, SQL projects, and model artifacts through CI/CD
- observe results through supported UIs and APIs

### 3.2 What you may not do

- use `docker exec`
- edit code inside a running container
- make learner changes directly in the protected infrastructure repository
- bypass review by manually updating a runtime asset

### 3.3 Why these rules exist

These restrictions teach three important realities:

1. runtime state is not a source of truth
2. platform infrastructure must stay stable and auditable
3. production change management is mostly about artifact flow, not shell access

## 4. Repository strategy analysis

You asked for a serious comparison between multi-repo and monorepo organization for the production-style workflow.

### 4.1 Option A: multiple dedicated repositories

Example layout:

- `platform-infra`
- `analytics-dbt`
- `feature-store`
- `ml-training`
- `ml-retraining` or `ml-batch-scoring`
- `ml-orchestration`
- `data-quality`

#### Benefits

- strong ownership boundaries
- clearer blast-radius control
- independent release cycles
- smaller pull requests per domain
- easier access control for sensitive repos

#### Costs

- more repositories to manage
- more repeated boilerplate
- cross-repo changes are slower
- version coordination becomes harder
- CI/CD has to pass versions between repos explicitly

#### When it makes sense

- different teams own dbt, orchestration, and ML code
- security or compliance requires tighter separation
- release cadence differs heavily by subsystem
- platform engineering wants strict protection around infrastructure

### 4.2 Option B: monorepo-style organization

Example layout:

- one delivery repo with internal directories for:
  - dbt
  - Feast
  - training
  - quality jobs
  - pipeline definitions

This is not the same as putting everything into the infrastructure repo without discipline. A good monorepo still needs ownership rules, directory boundaries, CI path filters, and release discipline.

#### Benefits

- easier discoverability
- simpler onboarding
- easier refactors across dbt, features, and training code
- one pull request can update all related assets together
- one CI system can validate dependency changes end to end

#### Costs

- weak boundaries if ownership rules are not enforced
- longer CI runs if path-aware pipelines are missing
- easier for unrelated teams to step on each other
- harder to grant very selective access

#### When it makes sense

- the project is small or medium in scale
- one team or a few closely aligned teams own the workflow
- changes often touch dbt, features, and training logic together
- the engineering group can maintain strong internal boundaries

### 4.3 Is monorepo viable in real production?

Yes. Monorepo is absolutely viable in real production environments.

However, it is only production-grade when it is managed deliberately. That means:

- clear directory ownership
- CODEOWNERS or equivalent review rules
- path-based CI/CD triggers
- release versioning by component
- internal package or image boundaries
- documentation that explains what can change together and what cannot

Without those controls, a monorepo turns into an unstructured shared folder. With those controls, it can be highly effective.

### 4.4 What is more common in industry?

There is no single universal answer.

What is common:

- platform infrastructure is often separated or protected more strictly than application logic
- data and ML delivery code may be split into multiple repos or grouped in a monorepo
- smaller companies and smaller teams often prefer fewer repos
- larger organizations more often split ownership across dedicated repos

### 4.5 CI/CD implications

#### Multi-repo

CI/CD typically:

- validates each repo independently
- publishes its own image or package
- exposes version outputs for downstream repos
- requires orchestration code or deployment manifests to reference those versions

This is clean but coordination-heavy.

#### Monorepo

CI/CD typically:

- runs only the checks relevant to changed directories
- builds only the changed images or packages
- can run integration tests across components more easily
- still needs a way to deploy only the affected services

This is simpler for cross-cutting changes but requires better CI design.

### 4.6 Recommendation for smaller but production-minded setups

For smaller and medium-scale teams, the most practical production-minded option is usually a hybrid:

- keep the infrastructure repo protected and separate
- use one delivery monorepo for dbt, Feast, training, quality, and related orchestration assets
- enforce ownership and path-based CI inside that delivery monorepo

Why this is a strong default:

- it keeps platform infrastructure stable
- it avoids creating too many small repos too early
- it still lets one change update dbt, features, and training together
- it fits the reality that smaller teams often share responsibility across the whole workflow

If the team grows and ownership becomes more specialized, the delivery monorepo can later be split.

## 5. Production repository responsibilities

Use this as the mental model for Lab 1.

| Repository type | What belongs there | What should not belong there |
|---|---|---|
| infrastructure repo | compose, Helm, Terraform, shared service config, networking, storage, secrets wiring | learner feature logic, ad hoc notebook code, live fixes |
| dbt repo | models, tests, docs, macros, profiles templates | Airflow platform config, random experiments |
| feature-store repo | Feast entities, sources, feature views, materialization jobs | unrelated training code |
| training repo | feature consumption logic, training code, evaluation code, model packaging | runtime platform wiring |
| orchestration repo | DAGs, workflow contracts, deployment references | raw modeling experiments |
| quality repo | Great Expectations suites, Evidently jobs, validation rules | unrelated feature engineering |

The actual names can differ, but the responsibility boundaries should stay clear.

## 6. End-to-end production workflow

This is the full lifecycle that Lab 1 teaches.

### 6.1 Step 1: inspect the current platform state

Before changing anything, learn what is already running.

Use these components:

- CloudBeaver to inspect `demo-postgres`
- Trino to inspect `iceberg.retail_raw` and `iceberg.analytics`
- dbt docs to understand model lineage
- MLflow to inspect previous training runs
- Feast UI to inspect available features
- Airflow to inspect the DAG structure

What you are learning at this stage:

- where the source data begins
- where transformed tables live
- where features are published
- where models are tracked
- where jobs are orchestrated

### 6.2 Step 2: choose the repository where the change belongs

Do not start by editing infrastructure.

Ask:

- am I changing analytics SQL? Then it belongs in the dbt repo.
- am I changing feature definitions? Then it belongs in the Feast repo.
- am I changing training code or model packaging? Then it belongs in the training repo.
- am I changing workflow sequencing? Then it belongs in the orchestration repo.
- am I changing validation rules? Then it belongs in the quality repo.

This is one of the most important production habits.

### 6.3 Step 3: develop the change locally in the correct repo

Examples:

- add a dbt model or test
- add a Feast feature view
- adjust model training code
- strengthen a Great Expectations rule

At this stage:

- write code
- run local repo-specific checks if available
- update documentation with the change
- avoid touching runtime containers directly

### 6.4 Step 4: open a pull request

The pull request should explain:

- what changed
- why it changed
- what datasets or services are affected
- what validation you expect CI to perform
- what downstream deployment effect should happen

For beginners, this may feel administrative, but in production it is how teams communicate change risk.

### 6.5 Step 5: let CI validate the change

What CI usually does by area:

#### dbt repo

- install dbt dependencies
- run `dbt parse`
- run `dbt build` against a validation environment
- generate docs metadata
- optionally build and publish a dbt runner image

#### feature-store repo

- validate Feast definitions
- run `feast apply` in a non-production environment
- verify materialization jobs or schemas

#### training repo

- run unit tests
- validate training code
- train or smoke-test on sample data
- build and publish a training image

#### quality repo

- validate expectation suites
- run Great Expectations checks
- build Evidently report generation artifacts

#### orchestration repo

- lint DAGs
- validate imports and schedule syntax
- update image tags or artifact references

### 6.6 Step 6: publish artifacts

This is where many beginners need the clearest explanation.

If CI passes, the change is turned into a deployable artifact. That might be:

- a dbt image
- a training image
- a quality image
- a versioned Python package
- a promoted model bundle

Those artifacts are then stored somewhere stable:

- a container registry
- object storage such as MinIO or cloud storage
- an artifact repository
- a model registry such as MLflow

### 6.7 Step 7: update the deployment layer

Publishing an artifact is not enough. The runtime must be told to use it.

Examples:

- Airflow DAG references a new image tag
- a deployment manifest points MLServer at a new model bundle
- a scheduled feature materialization job runs the new feature-store version

In a multi-repo setup this may happen in the orchestration or deployment repo.

In a monorepo setup it may happen in the same pull request, but it still should be a separate step in the pipeline logic.

### 6.8 Step 8: deploy and run the workflow

After approval, CD promotes the new version into the environment.

Then the learner or operator checks:

- Airflow DAG run status
- dbt model results
- Feast materialization state
- MLflow experiment outputs
- MLServer health
- Great Expectations docs
- Evidently report freshness

### 6.9 Step 9: observe the outcome across the platform

Do not stop at "the deployment succeeded."

A safe deployment also checks that the data and ML lifecycle is still coherent.

## 7. How each major platform component fits into Lab 1

This section ties the production workflow to the actual services the learner will encounter.

### 7.1 CloudBeaver

What it is:

- a browser-based SQL client

Why it exists:

- easy inspection of source tables and schemas

How the learner uses it:

- connect to `demo-postgres`
- inspect raw source tables such as `customers`, `orders`, and `support_tickets`
- verify source-side assumptions before changing dbt or feature logic

What to look at:

- row shapes
- null patterns
- source schema names
- raw status fields

Configuration versus usage versus observation:

- configure rarely in the lab
- use it for manual inspection
- observe raw data quality and shape

### 7.2 JupyterHub

What it is:

- the managed notebook environment

Why it exists:

- safe exploratory compute for analysts and ML practitioners

How the learner uses it:

- prototype SQL or Python exploration
- inspect data with notebooks
- test ideas before turning them into repo code

Important production rule:

- notebooks are for exploration, not for bypassing repository-based delivery

What to look at:

- environment variables
- access to Spark, Trino, and MLflow
- resource usage patterns

Read [JUPYTERHUB_GUIDE.md](./JUPYTERHUB_GUIDE.md) for environment management.

### 7.3 Spark and Spark workers

What Spark is:

- distributed compute for custom ingestion, feature preparation, and large processing tasks

Why it exists:

- source loading and larger transformations should not depend on local pandas workflows

How the learner uses or observes it:

- observe notebook-driven or custom Spark jobs
- open the Spark master and worker UIs
- confirm executor allocation, worker health, and job execution

What to inspect when debugging:

- whether workers are alive
- whether memory or CPU is saturated
- whether a job is stuck in scheduling

Configuration versus usage versus observation:

- configure cluster defaults in `spark-defaults.conf`
- use Spark from notebooks or orchestrated jobs
- observe worker and stage status in the UIs

### 7.4 Trino

What it is:

- the shared SQL engine

Why it exists:

- one query layer for both raw source data and lakehouse tables

How the learner uses it:

- validate raw ingestion
- query dbt outputs
- support BI and notebook access

What to inspect:

- whether schemas appear under `iceberg.retail_raw` and `iceberg.analytics`
- whether query results match expectations
- whether latency or query errors point to catalog problems

### 7.5 MinIO

What it is:

- the S3-compatible object store

Why it exists:

- it stores Iceberg files, Feast offline data, MLflow artifacts, and other generated assets

How the learner uses it:

- inspect feature parquet files
- inspect MLflow artifacts
- confirm generated assets were written

What to look at:

- `warehouse/` for lakehouse and feature-related data
- `mlflow-artifacts/` for tracked runs
- model bundle or monitoring-related outputs when relevant

### 7.6 Airflow

What it is:

- the orchestration system

Why it exists:

- it defines and observes the workflow order

How the learner uses it:

- inspect the `retail_ml_pipeline`
- view task dependencies
- trigger or observe runs after deployment

What to look at:

- `ingest_raw`
- `dbt_run_and_test`
- `publish_features_and_train`
- task logs and durations

### 7.7 Superset

What it is:

- the BI and dashboard layer

Why it exists:

- transformed data should become readable by business users, not only engineers

How the learner uses it:

- inspect the analytical results exposed through Trino-backed datasets
- verify that business-facing queries still work after a change

What to look at:

- whether transformed metrics still make sense
- whether dimensions and measures align with dbt outputs

### 7.8 Grafana and Prometheus

What they are:

- Prometheus collects metrics
- Grafana displays them

Why they exist:

- data platforms are software systems and need runtime monitoring

How the learner uses them:

- observe service health during or after a deployment
- inspect resource and database metrics

What to look at:

- PostgreSQL exporter metrics
- service uptime behavior
- spikes around heavy jobs

### 7.9 Great Expectations

What it is:

- the data validation framework

Why it exists:

- analytics and model training should depend on checked data, not assumptions

How the learner uses it:

- inspect Data Docs after a run
- confirm expectations still pass after a schema or logic change

What to look at:

- null checks
- range checks
- label set checks

### 7.10 Evidently

What it is:

- the monitoring report generator for data quality and drift

Why it exists:

- a model workflow should show how post-training monitoring works

How the learner uses it:

- open the generated report
- compare reference and current distributions

What to look at:

- drift signals
- feature distribution shifts
- suspicious prediction-probability changes

### 7.11 Feast

What it is:

- the feature store

Why it exists:

- feature definitions should be reusable and consistent across training and serving

How the learner uses it:

- inspect feature views
- verify materialized features
- ensure new definitions map to trusted upstream datasets

What to look at:

- entity keys
- source paths
- feature schemas
- freshness assumptions

### 7.12 MLflow

What it is:

- experiment and model tracking

Why it exists:

- training must be reproducible and reviewable

How the learner uses it:

- inspect run metrics and artifacts
- compare experiments
- verify the model artifact was logged

What to look at:

- run names
- accuracy or other metrics
- model artifact paths
- experiment separation

### 7.13 MLServer

What it is:

- the inference-serving layer

Why it exists:

- a platform is incomplete without a serving endpoint

How the learner uses it:

- confirm the model bundle is present
- call the inference API if the exercise includes serving validation

What to look at:

- model readiness
- endpoint health
- whether the served model matches the latest approved bundle

### 7.14 dbt docs

What it is:

- the dbt dashboard and documentation site

Why it exists:

- it shows lineage, tests, descriptions, and dependency structure

How the learner uses it:

- inspect how raw models lead into marts
- confirm a new model is documented and connected correctly

What to look at:

- lineage graph
- model descriptions
- test results
- dependencies into `customer_360`, `customer_behavior`, `product_performance`, and `churn_training_dataset`

## 8. Detailed workflow example

This walkthrough shows how one realistic change moves through the system.

### Scenario

You want to add a new customer-level signal that should appear in:

- dbt outputs
- Feast features
- model training
- quality validation

### 8.1 Update the dbt repository

You would:

1. create a branch in the dbt repo
2. update or add a model that computes the new signal
3. add tests and documentation
4. open a pull request

Expected CI outcome:

- dbt parse passes
- dbt build passes
- docs metadata is refreshed
- a new dbt image or package is published

### 8.2 Update the feature-store repository

You would:

1. update the Feast feature definitions
2. confirm the source field names match the dbt output
3. open a pull request

Expected CI outcome:

- Feast definitions validate
- feature registration succeeds in a validation environment

### 8.3 Update the training repository

You would:

1. update the training code to consume the new feature
2. adjust evaluation if needed
3. open a pull request

Expected CI outcome:

- tests pass
- training smoke test passes
- training image is published

### 8.4 Update the orchestration repository

You would:

1. update DAG references or environment values so Airflow uses the promoted artifact versions
2. deploy the DAG change

Expected CD outcome:

- the next DAG run uses the new dbt image, feature definitions, and training image

### 8.5 Validate the deployed result

Use the platform UIs in this order:

1. Airflow: confirm task success
2. dbt docs: confirm lineage and docs
3. Trino: confirm the new field exists
4. Great Expectations: confirm validation still passes
5. Feast UI: confirm the feature is registered
6. MLflow: confirm the new training run exists
7. MLServer: confirm serving still works
8. Evidently: inspect whether the new feature affects monitoring results
9. Grafana and Prometheus: confirm the system stayed healthy

## 9. What beginners should inspect in each component

Use this table as a quick operational checklist.

| Component | Beginner focus in Lab 1 |
|---|---|
| CloudBeaver | understand raw source tables before changing downstream logic |
| JupyterHub | prototype ideas, but treat notebooks as exploratory, not deployable truth |
| Spark | confirm distributed processing behavior for custom ETL or large data work |
| Spark worker UI | confirm worker availability and resource pressure |
| Trino | validate raw and transformed tables |
| MinIO | inspect parquet outputs and artifacts |
| Airflow | confirm orchestration order and task outcomes |
| Superset | validate business-facing analytical results |
| Grafana | observe health signals around deployments |
| Prometheus | inspect raw metrics when a dashboard suggests a problem |
| Great Expectations | verify dataset assumptions still pass |
| Evidently | inspect drift and monitoring behavior |
| Feast | verify feature definitions, sources, and materialization |
| MLflow | compare runs and inspect model artifacts |
| MLServer | verify model serving readiness |
| dbt docs | inspect lineage, model definitions, and test status |

## 10. Recommended production habit for this repo

If you want to use this repository as a starting point for a production-minded setup, the strongest default is:

1. keep this repository focused on platform infrastructure and reference implementation
2. create a separate delivery monorepo for dbt, Feast, training, and quality logic
3. publish images and artifacts through CI/CD
4. let Airflow and deployment configuration point to approved versions
5. use the running services for observation, not ad hoc modification

That gives you production realism without unnecessary repository sprawl.

## 11. End condition for Lab 1

You have completed Lab 1 successfully when you can explain:

- which repository owns each kind of change
- how a dbt change becomes a deployed artifact
- how a Feast change depends on upstream transformed data
- how training code becomes a model artifact and then a served model
- how Airflow coordinates the flow
- how to validate the outcome through Trino, dbt docs, Great Expectations, Feast, MLflow, MLServer, Evidently, Grafana, Prometheus, Superset, CloudBeaver, and JupyterHub

If you can explain those relationships without relying on shell access to a running container, you have learned the production operating model this lab is designed to teach.
