# Practice Lab

This document is meant to teach the stack as one connected system instead of a list of tools.

## Scenario

You have an external PostgreSQL database with ecommerce data. You want to ingest it, clean it, validate it, train a churn model, serve predictions, monitor drift, and visualize both business and operational metrics.

This repo already gives you a local version of that story using `demo-postgres`.

## Step 1: Start with the source database

Open CloudBeaver or connect directly with SQL to `demo-postgres`.

Look at these tables first:

- `customers`
- `orders`
- `order_items`
- `events`
- `payments`
- `shipments`
- `support_tickets`

What you are learning here:

- operational systems are normalized and event-oriented
- this is usually not the shape you want for BI or ML

## Step 2: Ingest raw data into the lakehouse

Open [notebooks/01_ingest_and_explore.py](/Users/rohan/Projects/netsol/ml-platform/notebooks/01_ingest_and_explore.py) in JupyterLab.

That Python walkthrough script reads PostgreSQL tables through JDBC and writes them into Iceberg as `warehouse.retail_raw.*`.

What Spark is doing here:

- pulling data from a source system
- writing structured tables into the lakehouse
- giving you distributed compute if the source grows

If you later replace `demo-postgres` with your real Postgres server, this is the first part you adapt.

To make those connection details repeatable across developers, do not keep editing notebook cells by hand:

- put shared JupyterHub environment variables in `docker-compose.yml` under the `jupyterhub` service
- forward those values into spawned notebook servers through `jupyterhub/jupyterhub_config.py`
- keep cluster-wide Spark defaults in `spark/conf/spark-defaults.conf`
- make walkthrough scripts read from environment variables instead of hardcoded hosts and passwords

See [docs/JUPYTERHUB_GUIDE.md](/Users/rohan/Projects/netsol/ml-platform/docs/JUPYTERHUB_GUIDE.md) for the full setup, including VS Code connectivity and guidance on `.py` versus `.ipynb` notebooks.

## Step 3: Transform raw tables with dbt

Open the dbt project in [dbt/retail](/Users/rohan/Projects/netsol/ml-platform/dbt/retail).

Key outputs:

- `customer_behavior`
- `customer_360`
- `product_performance`
- `churn_training_dataset`

What dbt is doing here:

- converting raw tables into analytics-ready marts
- centralizing business logic in versioned SQL
- testing assumptions like non-null keys and valid labels
- generating browsable docs

Use dbt when you want reproducible warehouse logic rather than ad hoc SQL in a learner script.

## Step 4: Query everything through Trino

Open [notebooks/04_query_with_trino.py](/Users/rohan/Projects/netsol/ml-platform/notebooks/04_query_with_trino.py) in JupyterLab.

Trino can query:

- `iceberg.analytics.*` for lakehouse tables
- `postgresql.public.*` for source tables

What Trino is doing here:

- giving you one SQL layer across multiple systems
- making Superset and dbt simpler because they can both use the same query engine

## Step 5: Validate data quality

There are two layers of validation in this repo:

- dbt tests for model-level guarantees
- Great Expectations for richer learner-facing dataset validation and Data Docs

Open `http://localhost:8091` after bootstrap finishes.

What Great Expectations is doing here:

- checking whether the marts match your assumptions
- publishing readable validation docs for humans

## Step 6: Register and materialize features in Feast

Open [feast/project/features.py](/Users/rohan/Projects/netsol/ml-platform/feast/project/features.py).

The feature views point at parquet data written from the analytics layer.

What Feast is doing here:

- turning curated analytics fields into reusable feature definitions
- reducing train/serve skew
- giving you an online feature lookup path later

## Step 7: Train and track a model

Open [notebooks/03_train_log_and_serve.py](/Users/rohan/Projects/netsol/ml-platform/notebooks/03_train_log_and_serve.py) in JupyterLab.

That Python walkthrough script trains a churn model from `iceberg.analytics.churn_training_dataset`, logs it to MLflow, and writes an MLServer model bundle.

What MLflow is doing here:

- storing run history
- comparing metrics and parameters
- preserving model artifacts

## Step 8: Serve the model

MLServer serves `churn-model` on `http://localhost:8085/v2/models/churn-model`.

What MLServer is doing here:

- exposing the model as an inference API
- turning a trained artifact into something other applications can call

Try an inference request once the stack is up:

```bash
curl -X POST http://localhost:8085/v2/models/churn-model/infer \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": [{
      "name": "predict",
      "shape": [1, 8],
      "datatype": "FP32",
      "data": [[32, 5, 720.0, 144.0, 18, 12, 0, 0.0]]
    }]
  }'
```

## Step 9: Monitor the data and model

Open `http://localhost:8092`.

What Evidently is doing here:

- comparing a reference dataset with a current dataset
- helping you reason about drift and monitoring

In a real project, this would run repeatedly on fresh production batches.

## Step 10: Visualize analytics and platform health

Use Superset for business analytics and Grafana for platform metrics.

Superset:

- explore business tables through SQL and dashboards
- connect it to Trino for lakehouse analytics

Grafana:

- inspect container CPU and memory
- inspect demo Postgres activity through Prometheus exporters

## If you replace the demo source with your real PostgreSQL

The minimum path is:

1. update the JDBC connection details in the ingestion walkthrough script or bootstrap logic
2. ingest the source tables into Iceberg
3. adapt the dbt models to your schema
4. adjust Great Expectations suites and Feast feature views
5. retrain and re-log models in MLflow
6. update Superset dashboards and Evidently monitoring inputs

That is the core mental model of the stack.
