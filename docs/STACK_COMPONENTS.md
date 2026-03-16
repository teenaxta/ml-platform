# Stack Components

This repo uses one retail analytics and churn-prediction storyline. Each component has a clear role in that flow.

## Source and storage layer

### demo-postgres

This is the operational source system. It contains customers, products, orders, order items, events, payments, shipments, and support tickets.

Use it when you want to understand what a real OLTP source looks like before any ML work begins.

### MinIO

MinIO is the S3-compatible object store. It stores the Iceberg warehouse, Feast parquet files, and MLflow artifacts.

Use it as the local stand-in for cloud object storage.

### Iceberg REST catalog

The Iceberg REST service is the catalog for your lakehouse tables. Spark writes tables through it, and Trino reads those tables through its Iceberg connector.

Use it to understand how table metadata is managed separately from the files themselves.

## Compute and transformation layer

### Spark

Spark provides distributed processing for custom ETL, model preparation, and notebook-driven large-table work. In this teaching stack the default seeded bootstrap path is intentionally lightweight, but Spark remains the main distributed compute engine available to users.

Use Spark when data volume or transformation complexity is too large for simple pandas work.

### Trino

Trino is the SQL query layer across multiple systems. Here it queries both Iceberg tables and the source PostgreSQL database.

Use Trino when you want one SQL engine for analytics, ad hoc joins, BI tooling, and dbt execution.

### dbt

dbt turns raw lakehouse tables into analytics marts. In this repo the `dbt/retail` project builds `customer_360`, `customer_behavior`, `product_performance`, and `churn_training_dataset`.

Use dbt for versioned SQL transformations, tests, documentation, and repeatable analytics logic.

### dbt docs

The dbt docs site is the dashboard for understanding model lineage, descriptions, tests, and dependencies.

Use it when you want to understand how raw tables become analytical marts, or when you need to verify that a model change is documented and connected correctly.

### Airflow

Airflow orchestrates the end-to-end workflow. The `retail_ml_pipeline` DAG calls the same shared bootstrap logic that seeds the demo stack.

Use Airflow when you want scheduled and observable execution of your data and ML pipeline steps.

## Feature, experimentation, and serving layer

### Feast

Feast is the feature store. It registers reusable features and materializes them from parquet into an online store for low-latency access.

Use Feast when you want training and serving to use the same feature definitions.

### MLflow

MLflow tracks experiments, metrics, parameters, artifacts, and model versions.
This stack also enables MLflow GenAI server support so the AI Gateway page can manage provider credentials from the tracking server.

Use MLflow while training and comparing models, or when you want reproducibility around runs.

### MLServer

MLServer exposes trained models as inference endpoints. In this repo it serves the `churn-model` bundle created by the bootstrap flow.

Use MLServer when you want a simple local inference endpoint to test the last mile of the ML lifecycle.

## Data quality, monitoring, and BI

### Great Expectations

Great Expectations validates your prepared datasets and publishes Data Docs. In this repo it validates the learner-facing analytics datasets after dbt builds them.

Use it to encode assumptions about data quality beyond simple SQL tests.

### Evidently

Evidently generates model and data monitoring reports. Here it compares a reference batch and a drifted current batch for the churn use case.

Use it to understand drift, stability, and production monitoring concepts.

### Superset

Superset is the BI layer. It is bootstrapped with sample content so you can learn the UI, and it is positioned to sit on top of Trino for warehouse analytics.

Use Superset to build charts, dashboards, and SQL-based explorations.

### Prometheus and Grafana

Prometheus scrapes runtime metrics, and Grafana visualizes them. This stack currently includes Prometheus itself and a Postgres exporter so you can monitor the platform and the demo database activity.

Use them to understand operational observability for the platform itself, not just the business data inside it.

### CloudBeaver

CloudBeaver is the general-purpose SQL UI. It is useful for browsing the source database or connecting to other databases without leaving the browser.

Use it when you want quick schema browsing or manual SQL access.

### JupyterHub

JupyterHub is the interactive workspace for notebooks and notebook-style `.py` walkthroughs. The repo includes learner scripts that follow the same data flow as the rest of the platform, and it can inject shared environment defaults so each developer does not need to re-enter Spark, Trino, or MLflow settings by hand.

Use it for exploration, experiments, prototyping, and learning.
