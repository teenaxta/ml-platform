# Practice Lab 1

## Production-Style Delivery Monorepo

In this lab, you will build an end-to-end customer churn workflow in a separate delivery monorepo. You will create dbt models, feature definitions, training code, model-serving packaging, quality checks, an Airflow DAG, and CI/CD workflows. The running `ml-platform` repository remains the platform runtime. Your delivery repository is where you write the business and ML code.

By the end of this lab you will have produced:

- a new Git repository named `customer-churn-delivery`
- a dbt project that builds the churn dataset from the demo PostgreSQL source
- Feast feature definitions for customer features
- a training script that logs runs to MLflow and writes an MLServer bundle
- Great Expectations and Evidently outputs
- an Airflow DAG that orchestrates the workflow
- a GitHub Actions workflow that validates, packages, deploys, and verifies the change

Systems you will touch:

- CloudBeaver
- JupyterHub
- Spark and the Spark worker UI
- Trino
- MinIO
- Airflow
- Superset
- Grafana
- Prometheus
- Great Expectations
- Evidently
- Feast
- MLflow
- MLServer
- dbt docs

## 1. Create the delivery repository

### Goal of this section

Create the separate monorepo that will hold all learner-written code for the production-style workflow.

### What you will create or change

- a new repository folder on disk
- the full folder structure for dbt, Feast, training, quality, MLServer, Airflow, and CI/CD

### Exact steps

1. Create the repository next to `ml-platform`:

```bash
cd ~/Projects/netsol
mkdir -p customer-churn-delivery
cd customer-churn-delivery
git init
mkdir -p .github/workflows
mkdir -p dbt/churn_lab/models/staging
mkdir -p dbt/churn_lab/models/marts
mkdir -p feast/project
mkdir -p training
mkdir -p quality
mkdir -p airflow/dags
mkdir -p mlserver/models/churn-model
```

2. Create a `.gitignore` file:

```text
__pycache__/
.pytest_cache/
.venv/
dbt/churn_lab/target/
dbt/churn_lab/logs/
mlserver/models/churn-model/model.joblib
great_expectations/uncommitted/
evidently/reports/
```

3. Commit the empty scaffold:

```bash
git checkout -b workshop/lab1-start
git add .
git commit -m "lab1: create delivery monorepo scaffold"
```

### What CI/CD or the platform does next

Nothing yet. You have not created any workflows.

### How to verify

- Run `find . -maxdepth 3 -type d | sort`.
- Confirm you can see `dbt/churn_lab`, `feast/project`, `training`, `quality`, `airflow/dags`, and `.github/workflows`.

### Common mistakes

- Creating the repo inside `ml-platform`. Do not do that in Lab 1.
- Forgetting `.github/workflows`. If that folder is missing, your CI file later has nowhere to go.

## 2. Build the dbt project from scratch

### Goal of this section

Create the SQL transformation layer that turns the raw source data into analytics-ready tables and a churn training dataset.

### What you will create or change

- `dbt/profiles.yml`
- `dbt/churn_lab/dbt_project.yml`
- `dbt/churn_lab/models/sources.yml`
- six staging model files
- four mart model files
- one schema YAML file for model tests and descriptions

### Exact steps

1. Create `dbt/profiles.yml`:

```yaml
churn_lab:
  target: dev
  outputs:
    dev:
      type: trino
      method: none
      host: trino
      port: 8080
      user: trino
      catalog: iceberg
      schema: analytics
      threads: 4
      http_scheme: http
```

2. Create `dbt/churn_lab/dbt_project.yml`:

```yaml
name: churn_lab
version: 1.0.0
config-version: 2

profile: churn_lab

model-paths: ["models"]
seed-paths: ["seeds"]
test-paths: ["tests"]
macro-paths: ["macros"]
target-path: "target"
clean-targets: ["target", "dbt_packages"]

models:
  churn_lab:
    staging:
      +materialized: table
    marts:
      +materialized: table

vars:
  lab_snapshot_date: '2024-03-01'
```

3. Create `dbt/churn_lab/models/sources.yml`:

```yaml
version: 2

sources:
  - name: retail_raw
    database: postgresql
    schema: public
    tables:
      - name: customers
      - name: orders
      - name: order_items
      - name: products
      - name: events
      - name: support_tickets
```

4. Create `dbt/churn_lab/models/staging/stg_customers.sql`:

```sql
select
  customer_id,
  first_name,
  last_name,
  email,
  country,
  age,
  signup_date,
  is_premium
from {{ source('retail_raw', 'customers') }}
```

5. Create `dbt/churn_lab/models/staging/stg_orders.sql`:

```sql
select
  order_id,
  customer_id,
  cast(order_date as timestamp) as order_date,
  status,
  cast(total_amount as double) as total_amount
from {{ source('retail_raw', 'orders') }}
```

6. Create `dbt/churn_lab/models/staging/stg_order_items.sql`:

```sql
select
  item_id,
  order_id,
  product_id,
  quantity,
  cast(unit_price as double) as unit_price
from {{ source('retail_raw', 'order_items') }}
```

7. Create `dbt/churn_lab/models/staging/stg_products.sql`:

```sql
select
  product_id,
  name,
  category,
  cast(unit_price as double) as unit_price,
  stock_qty
from {{ source('retail_raw', 'products') }}
```

8. Create `dbt/churn_lab/models/staging/stg_events.sql`:

```sql
select
  event_id,
  customer_id,
  event_type,
  cast(event_ts as timestamp) as event_ts
from {{ source('retail_raw', 'events') }}
```

9. Create `dbt/churn_lab/models/staging/stg_support_tickets.sql`:

```sql
select
  ticket_id,
  customer_id,
  issue_type,
  priority,
  status,
  cast(created_at as timestamp) as created_at,
  cast(resolved_at as timestamp) as resolved_at
from {{ source('retail_raw', 'support_tickets') }}
```

10. Create `dbt/churn_lab/models/marts/customer_behavior.sql`:

```sql
with events as (
  select * from {{ ref('stg_events') }}
)

select
  customer_id,
  count_if(event_type = 'page_view') as page_views_30d,
  count_if(event_type = 'add_to_cart') as add_to_cart_30d,
  count_if(event_type = 'checkout') as checkout_events_30d,
  count_if(event_type = 'support_ticket') as support_tickets,
  case
    when count_if(event_type = 'add_to_cart') = 0 then 0.0
    else cast(count_if(event_type = 'checkout') as double) / cast(count_if(event_type = 'add_to_cart') as double)
  end as checkout_rate,
  cast('{{ var("lab_snapshot_date") }}' as timestamp) as event_timestamp
from events
group by 1
```

11. Create `dbt/churn_lab/models/marts/product_performance.sql`:

```sql
with products as (
  select * from {{ ref('stg_products') }}
),
items as (
  select * from {{ ref('stg_order_items') }}
)

select
  p.product_id,
  p.name,
  p.category,
  p.unit_price,
  p.stock_qty,
  count(i.item_id) as times_ordered,
  coalesce(sum(i.quantity), 0) as units_sold,
  coalesce(sum(i.quantity * i.unit_price), 0.0) as revenue,
  cast('{{ var("lab_snapshot_date") }}' as timestamp) as event_timestamp
from products p
left join items i on p.product_id = i.product_id
group by 1, 2, 3, 4, 5
```

12. Create `dbt/churn_lab/models/marts/customer_360.sql`:

```sql
with customers as (
  select * from {{ ref('stg_customers') }}
),
orders as (
  select * from {{ ref('stg_orders') }}
),
support as (
  select * from {{ ref('stg_support_tickets') }}
),
behavior as (
  select * from {{ ref('customer_behavior') }}
),
orders_agg as (
  select
    customer_id,
    count(*) as total_orders,
    sum(case when status = 'completed' then total_amount else 0 end) as lifetime_value,
    avg(case when status = 'completed' then total_amount end) as avg_order_value,
    date_diff('day', cast(max(order_date) as date), cast('{{ var("lab_snapshot_date") }}' as date)) as days_since_last_order,
    sum(case when status = 'returned' then 1 else 0 end) * 1.0 / nullif(count(*), 0) as return_rate
  from orders
  group by 1
),
support_agg as (
  select
    customer_id,
    count(*) as opened_tickets
  from support
  group by 1
)

select
  c.customer_id,
  c.first_name,
  c.last_name,
  c.email,
  c.country,
  c.age,
  c.signup_date,
  c.is_premium,
  coalesce(o.total_orders, 0) as total_orders,
  coalesce(o.lifetime_value, 0.0) as lifetime_value,
  coalesce(o.avg_order_value, 0.0) as avg_order_value,
  coalesce(o.days_since_last_order, 999) as days_since_last_order,
  coalesce(o.return_rate, 0.0) as return_rate,
  coalesce(s.opened_tickets, 0) as support_tickets,
  coalesce(b.page_views_30d, 0) as page_views_30d,
  coalesce(b.add_to_cart_30d, 0) as add_to_cart_30d,
  coalesce(b.checkout_events_30d, 0) as checkout_events_30d,
  coalesce(b.checkout_rate, 0.0) as checkout_rate,
  case
    when coalesce(o.days_since_last_order, 999) > 35
      or coalesce(s.opened_tickets, 0) >= 2
      or coalesce(o.return_rate, 0.0) >= 0.30
    then 1
    else 0
  end as churn_label,
  cast('{{ var("lab_snapshot_date") }}' as timestamp) as event_timestamp
from customers c
left join orders_agg o on c.customer_id = o.customer_id
left join support_agg s on c.customer_id = s.customer_id
left join behavior b on c.customer_id = b.customer_id
```

13. Create `dbt/churn_lab/models/marts/churn_training_dataset.sql`:

```sql
select
  customer_id,
  age,
  total_orders,
  lifetime_value,
  avg_order_value,
  days_since_last_order,
  page_views_30d,
  support_tickets,
  return_rate,
  churn_label,
  event_timestamp
from {{ ref('customer_360') }}
```

14. Create `dbt/churn_lab/models/marts/schema.yml`:

```yaml
version: 2

models:
  - name: customer_360
    description: Customer-level mart for churn analysis and feature generation.
    columns:
      - name: customer_id
        tests: [not_null, unique]
      - name: total_orders
        tests: [not_null]
      - name: lifetime_value
        tests: [not_null]
      - name: churn_label
        tests:
          - accepted_values:
              arguments:
                values: [0, 1]
                quote: false
  - name: customer_behavior
    description: Event-based customer engagement aggregates.
  - name: product_performance
    description: Product-level revenue and unit sales output for BI.
  - name: churn_training_dataset
    description: Final training matrix for model training and monitoring.
```

15. Run the dbt build from the delivery repository root:

```bash
docker run --rm --network mlplatform \
  -v "$PWD/dbt:/opt/dbt" \
  -w /opt/dbt \
  ghcr.io/dbt-labs/dbt-trino:1.8.latest \
  bash -lc "dbt deps --project-dir /opt/dbt/churn_lab --profiles-dir /opt/dbt && dbt run --project-dir /opt/dbt/churn_lab --profiles-dir /opt/dbt && dbt test --project-dir /opt/dbt/churn_lab --profiles-dir /opt/dbt && dbt docs generate --project-dir /opt/dbt/churn_lab --profiles-dir /opt/dbt"
```

### What CI/CD or the platform does next

Later, the workflow will rerun these exact dbt commands on the self-hosted runner and package `dbt/churn_lab/target/` as a deployable docs artifact.

### How to verify

1. In CloudBeaver, create a new Trino connection:

```text
Host: trino
Port: 8080
User: trino
```

2. In the Trino SQL editor, run:

```sql
select count(*) from iceberg.analytics.customer_360;
select count(*) from iceberg.analytics.churn_training_dataset;
select churn_label, count(*) from iceberg.analytics.churn_training_dataset group by 1 order by 1;
select product_id, name, revenue from iceberg.analytics.product_performance order by revenue desc limit 5;
```

Expected signals:

- `customer_360` has `15` rows
- `churn_training_dataset` has `15` rows
- `churn_label` split is `8` rows with `0` and `7` rows with `1`
- `Standing Desk Converter` is the highest-revenue product at `449.97`

3. Open the dbt docs page later, after deployment, and search for `customer_360`.

### Common mistakes

- Using `current_date` in the churn label. Do not do that. It makes the label drift over time and breaks the expected counts.
- Pointing dbt at `iceberg.retail_raw` instead of the PostgreSQL source. In this lab you are building the transformation repo directly from the source database.

## 3. Create Feast definitions and model training code

### Goal of this section

Create reusable feature definitions, train the churn model, log it in MLflow, and package it for MLServer.

### What you will create or change

- `feast/project/feature_store.yaml`
- `feast/project/features.py`
- `training/train_churn_model.py`
- `mlserver/models/churn-model/model-settings.json`
- `mlserver/Dockerfile`

### Exact steps

1. Create `feast/project/feature_store.yaml`:

```yaml
project: churn_lab
provider: local

registry:
  registry_type: sql
  path: postgresql+psycopg://feast:${FEAST_DB_PASSWORD}@postgres-feast:5432/feast
  cache_ttl_seconds: 60

offline_store:
  type: file

online_store:
  type: postgres
  host: postgres-feast
  port: 5432
  database: feast
  user: feast
  password: ${FEAST_DB_PASSWORD}
  pgvector_enabled: true
  vector_len: 512

entity_key_serialization_version: 2
```

2. Create `feast/project/features.py`:

```python
import os
from datetime import timedelta

from feast import Entity, FeatureView, Field, FileSource, ValueType
from feast.data_format import ParquetFormat
from feast.types import Float64, Int64


S3_ENDPOINT = os.getenv("AWS_S3_ENDPOINT_URL", "http://localhost:9000")

customer = Entity(
    name="customer",
    join_keys=["customer_id"],
    value_type=ValueType.INT64,
    description="Customer primary key",
)

customer_stats_source = FileSource(
    name="customer_stats_source",
    path="s3://warehouse/feast/customer_stats/",
    file_format=ParquetFormat(),
    timestamp_field="event_timestamp",
    s3_endpoint_override=S3_ENDPOINT,
)

customer_behavior_source = FileSource(
    name="customer_behavior_source",
    path="s3://warehouse/feast/customer_behavior/",
    file_format=ParquetFormat(),
    timestamp_field="event_timestamp",
    s3_endpoint_override=S3_ENDPOINT,
)

customer_stats = FeatureView(
    name="customer_stats",
    entities=[customer],
    ttl=timedelta(days=30),
    schema=[
        Field(name="total_orders", dtype=Int64),
        Field(name="lifetime_value", dtype=Float64),
        Field(name="avg_order_value", dtype=Float64),
        Field(name="days_since_last_order", dtype=Int64),
    ],
    source=customer_stats_source,
)

customer_behavior = FeatureView(
    name="customer_behavior",
    entities=[customer],
    ttl=timedelta(days=30),
    schema=[
        Field(name="page_views_30d", dtype=Int64),
        Field(name="support_tickets", dtype=Int64),
        Field(name="return_rate", dtype=Float64),
    ],
    source=customer_behavior_source,
)
```

3. Create `training/train_churn_model.py`:

```python
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import joblib
import mlflow
import pandas as pd
import pyarrow as pa
import pyarrow.fs as pa_fs
import pyarrow.parquet as pq
import trino
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "mlserver" / "models" / "churn-model"
S3_ENDPOINT = os.environ.get("AWS_S3_ENDPOINT_URL", "http://localhost:9000")


def trino_query(sql: str) -> pd.DataFrame:
    conn = trino.dbapi.connect(
        host="trino",
        port=8080,
        user="trino",
        catalog="iceberg",
        schema="analytics",
    )
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=[d[0] for d in cur.description])


def s3_filesystem() -> pa_fs.S3FileSystem:
    parsed = urlparse(S3_ENDPOINT)
    return pa_fs.S3FileSystem(
        access_key=os.environ["AWS_ACCESS_KEY_ID"],
        secret_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region="us-east-1",
        scheme=parsed.scheme or "http",
        endpoint_override=parsed.netloc or parsed.path,
    )


def write_parquet(df: pd.DataFrame, uri: str) -> None:
    parsed = urlparse(uri)
    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/").rstrip("/")
    fs = s3_filesystem()
    dataset_path = f"{bucket}/{prefix}"
    fs.delete_dir_contents(dataset_path, missing_dir_ok=True)
    fs.create_dir(dataset_path, recursive=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    with fs.open_output_stream(f"{dataset_path}/part-00000.parquet") as sink:
        pq.write_table(table, sink)


def main() -> None:
    customer_360 = trino_query("select * from iceberg.analytics.customer_360 order by customer_id")
    training_df = trino_query("select * from iceberg.analytics.churn_training_dataset order by customer_id")

    write_parquet(
        customer_360[
            [
                "customer_id",
                "total_orders",
                "lifetime_value",
                "avg_order_value",
                "days_since_last_order",
                "event_timestamp",
            ]
        ],
        "s3://warehouse/feast/customer_stats/",
    )

    write_parquet(
        customer_360[
            [
                "customer_id",
                "page_views_30d",
                "support_tickets",
                "return_rate",
                "event_timestamp",
            ]
        ],
        "s3://warehouse/feast/customer_behavior/",
    )

    feature_columns = [
        "age",
        "total_orders",
        "lifetime_value",
        "avg_order_value",
        "days_since_last_order",
        "page_views_30d",
        "support_tickets",
        "return_rate",
    ]

    X = training_df[feature_columns]
    y = training_df["churn_label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )

    model = RandomForestClassifier(n_estimators=50, random_state=42)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    accuracy = float(accuracy_score(y_test, preds))
    f1 = float(f1_score(y_test, preds))

    mlflow.set_tracking_uri("http://mlflow:5000")
    mlflow.set_experiment("lab1-customer-churn")

    with mlflow.start_run(run_name="lab1-random-forest"):
        mlflow.log_params({"model_type": "RandomForestClassifier", "n_estimators": 50})
        mlflow.log_metrics({"accuracy": accuracy, "f1_score": f1})

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_DIR / "model.joblib")
    (MODEL_DIR / "model-settings.json").write_text(
        json.dumps(
            {
                "name": "churn-model",
                "implementation": "mlserver_sklearn.SKLearnModel",
                "parameters": {"uri": "./model.joblib", "version": "v1"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
```

4. Create `mlserver/models/churn-model/model-settings.json`:

```json
{
  "name": "churn-model",
  "implementation": "mlserver_sklearn.SKLearnModel",
  "parameters": {
    "uri": "./model.joblib",
    "version": "v1"
  }
}
```

5. Create `mlserver/Dockerfile`:

```dockerfile
FROM seldonio/mlserver:1.4.0

COPY models /opt/mlserver/models
COPY settings.json /opt/mlserver/settings.json

ENV MLSERVER_MODELS_DIR=/opt/mlserver/models
CMD ["mlserver", "start", "/opt/mlserver/settings.json"]
```

6. Create `mlserver/settings.json`:

```json
{
  "debug": false,
  "parallel_workers": 1,
  "http_port": 8080,
  "grpc_port": 8081
}
```

7. Run the trainer locally:

```bash
docker run --rm --network mlplatform \
  -v "$PWD:/workspace" \
  -w /workspace \
  -e AWS_ACCESS_KEY_ID=mlplatform \
  -e AWS_SECRET_ACCESS_KEY=MinioSecure123 \
  -e AWS_S3_ENDPOINT_URL=http://minio:9000 \
  python:3.11-slim \
  bash -lc "pip install --quiet pandas pyarrow trino mlflow scikit-learn joblib && python training/train_churn_model.py"
```

8. Apply the Feast definitions:

```bash
docker run --rm --network mlplatform \
  -v "$PWD/feast/project:/opt/feast/project" \
  -w /opt/feast/project \
  -e FEAST_DB_PASSWORD="${FEAST_DB_PASSWORD:?set FEAST_DB_PASSWORD from the platform .env first}" \
  -e AWS_ACCESS_KEY_ID=mlplatform \
  -e AWS_SECRET_ACCESS_KEY=MinioSecure123 \
  -e AWS_S3_ENDPOINT_URL=http://minio:9000 \
  python:3.11-slim \
  bash -lc "pip install --quiet 'feast[postgres,aws]==0.40.1' pyarrow pandas psycopg2-binary pgvector s3fs && feast apply"
```

### What CI/CD or the platform does next

The workflow later repeats this sequence:

1. run the training script
2. write the Feast parquet files into MinIO under `s3://warehouse/feast/`
3. register the feature views
4. build the MLServer image
5. push the image to GHCR

### How to verify

1. Open MinIO Console at `http://localhost:9001`.
2. Open the `warehouse` bucket.
3. Open `feast/customer_stats/` and `feast/customer_behavior/`.
4. Confirm each folder contains a parquet file.
5. Open Feast UI at `http://localhost:6567`.
6. Confirm the `customer` entity exists.
7. Confirm feature views `customer_stats` and `customer_behavior` exist.
8. Open MLflow at `http://localhost:5000`.
9. Confirm experiment `lab1-customer-churn` exists and contains a run named `lab1-random-forest`.

### Common mistakes

- Writing Feast parquet files to the wrong bucket path. The exact path must start with `s3://warehouse/feast/`.
- Forgetting to create the `customer` entity. If the entity is missing, the feature views will not register correctly.
- Logging the model to MLflow but forgetting to write the MLServer bundle. In that case the run succeeds but deployment later fails.

## 4. Create quality and orchestration code

### Goal of this section

Create the data-quality outputs and the Airflow DAG that ties the workflow together.

### What you will create or change

- `quality/generate_quality_assets.py`
- `airflow/dags/churn_workshop_pipeline.py`

### Exact steps

1. Create `quality/generate_quality_assets.py`:

```python
from __future__ import annotations

from pathlib import Path

import pandas as pd
import trino
from evidently.metric_preset import DataDriftPreset, DataQualityPreset
from evidently.report import Report
from great_expectations.data_context import FileDataContext


ROOT = Path(__file__).resolve().parents[1]
GE_ROOT = ROOT / "great_expectations"
GE_DATA = GE_ROOT / "data"
EVIDENTLY_REPORTS = ROOT / "evidently" / "reports"


def trino_query(sql: str) -> pd.DataFrame:
    conn = trino.dbapi.connect(
        host="trino",
        port=8080,
        user="trino",
        catalog="iceberg",
        schema="analytics",
    )
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=[d[0] for d in cur.description])


def build_ge_docs() -> None:
    GE_DATA.mkdir(parents=True, exist_ok=True)
    customer_360 = trino_query("select * from iceberg.analytics.customer_360")
    churn_training = trino_query("select * from iceberg.analytics.churn_training_dataset")

    customer_360.to_csv(GE_DATA / "customer_360.csv", index=False)
    churn_training.to_csv(GE_DATA / "churn_training_dataset.csv", index=False)

    context = FileDataContext.create(project_root_dir=str(GE_ROOT))
    datasource = context.sources.add_or_update_pandas_filesystem(
        name="retail_files",
        base_directory=str(GE_DATA),
    )
    customer_asset = datasource.add_csv_asset(name="customer_360", batching_regex=r"customer_360\.csv")
    churn_asset = datasource.add_csv_asset(name="churn_training_dataset", batching_regex=r"churn_training_dataset\.csv")

    suites = {
        "customer_360_suite": customer_asset.build_batch_request(),
        "churn_training_suite": churn_asset.build_batch_request(),
    }

    for suite_name, batch_request in suites.items():
        suite = context.add_or_update_expectation_suite(expectation_suite_name=suite_name)
        validator = context.get_validator(
            batch_request=batch_request,
            expectation_suite_name=suite.expectation_suite_name,
        )
        validator.expect_column_values_to_not_be_null("customer_id")
        if "total_orders" in validator.columns():
            validator.expect_column_values_to_be_between("total_orders", min_value=0)
        if "lifetime_value" in validator.columns():
            validator.expect_column_values_to_be_between("lifetime_value", min_value=0)
        if "churn_label" in validator.columns():
            validator.expect_column_distinct_values_to_be_in_set("churn_label", [0, 1])
        validator.save_expectation_suite(discard_failed_expectations=False)
        context.add_or_update_checkpoint(
            name=f"{suite_name}_checkpoint",
            validations=[
                {
                    "batch_request": batch_request,
                    "expectation_suite_name": suite.expectation_suite_name,
                }
            ],
        )
        context.run_checkpoint(checkpoint_name=f"{suite_name}_checkpoint")

    context.build_data_docs()


def build_evidently_report() -> None:
    EVIDENTLY_REPORTS.mkdir(parents=True, exist_ok=True)
    scored = trino_query("select * from iceberg.analytics.churn_training_dataset order by customer_id")
    scored["prediction"] = scored["churn_label"]
    scored["prediction_probability"] = 0.85

    reference = scored.iloc[:7].copy()
    current = scored.iloc[7:].copy()
    current["avg_order_value"] = current["avg_order_value"] * 1.15

    report = Report(metrics=[DataQualityPreset(), DataDriftPreset()])
    report.run(reference_data=reference, current_data=current)
    report.save_html(str(EVIDENTLY_REPORTS / "index.html"))


if __name__ == "__main__":
    build_ge_docs()
    build_evidently_report()
```

2. Create `airflow/dags/churn_workshop_pipeline.py`:

```python
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    "owner": "workshop",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="churn_workshop_pipeline",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["workshop", "churn"],
) as dag:
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command="dbt deps --project-dir /opt/dbt/churn_lab --profiles-dir /opt/dbt && dbt run --project-dir /opt/dbt/churn_lab --profiles-dir /opt/dbt && dbt test --project-dir /opt/dbt/churn_lab --profiles-dir /opt/dbt && dbt docs generate --project-dir /opt/dbt/churn_lab --profiles-dir /opt/dbt",
    )

    train_model = BashOperator(
        task_id="train_model",
        bash_command="python /opt/platform/training/train_churn_model.py",
    )

    quality = BashOperator(
        task_id="quality",
        bash_command="python /opt/platform/quality/generate_quality_assets.py",
    )

    dbt_build >> train_model >> quality
```

### What CI/CD or the platform does next

The deployment job later copies this DAG into the platform `airflow/dags/` directory and restarts Airflow. Airflow then shows `churn_workshop_pipeline` in the DAG list.

### How to verify

1. Run the quality script:

```bash
docker run --rm --network mlplatform \
  -v "$PWD:/workspace" \
  -w /workspace \
  python:3.11-slim \
  bash -lc "pip install --quiet pandas trino great-expectations evidently && python quality/generate_quality_assets.py"
```

2. Open Great Expectations at `http://localhost:8091` after deployment and confirm:

- `customer_360_suite` appears
- `churn_training_suite` appears
- both rows show success

3. Open Evidently at `http://localhost:8092` and confirm the report renders.

### Common mistakes

- Saving Data Docs to the wrong directory. The deploy job expects `great_expectations/uncommitted/data_docs/local_site/`.
- Creating the DAG but forgetting that Airflow only sees files copied into the platform repo.

## 5. Create the CI/CD workflow

### Goal of this section

Create one workflow that validates pull requests and deploys after merge to `main`.

### What you will create or change

- `.github/workflows/churn_lab.yml`

### Exact steps

Create `.github/workflows/churn_lab.yml`:

```yaml
name: churn-lab

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

env:
  PLATFORM_ROOT: /srv/ml-platform
  IMAGE_NAME: ghcr.io/${{ github.repository_owner }}/${{ github.event.repository.name }}/churn-mlserver

jobs:
  validate:
    runs-on: [self-hosted]
    steps:
      - uses: actions/checkout@v4

      - name: Validate dbt
        run: |
          docker run --rm --network mlplatform \
            -v "$PWD/dbt:/opt/dbt" \
            -w /opt/dbt \
            ghcr.io/dbt-labs/dbt-trino:1.8.latest \
            bash -lc "dbt deps --project-dir /opt/dbt/churn_lab --profiles-dir /opt/dbt && dbt run --project-dir /opt/dbt/churn_lab --profiles-dir /opt/dbt && dbt test --project-dir /opt/dbt/churn_lab --profiles-dir /opt/dbt && dbt docs generate --project-dir /opt/dbt/churn_lab --profiles-dir /opt/dbt"

      - name: Train model and write Feast parquet
        run: |
          docker run --rm --network mlplatform \
            -v "$PWD:/workspace" \
            -w /workspace \
            -e AWS_ACCESS_KEY_ID=mlplatform \
            -e AWS_SECRET_ACCESS_KEY=MinioSecure123 \
            -e AWS_S3_ENDPOINT_URL=http://minio:9000 \
            python:3.11-slim \
            bash -lc "pip install --quiet pandas pyarrow trino mlflow scikit-learn joblib && python training/train_churn_model.py"

      - name: Apply Feast definitions
        run: |
          docker run --rm --network mlplatform \
            -v "$PWD/feast/project:/opt/feast/project" \
            -w /opt/feast/project \
            -e FEAST_DB_PASSWORD=${{ secrets.FEAST_DB_PASSWORD }} \
            -e AWS_ACCESS_KEY_ID=mlplatform \
            -e AWS_SECRET_ACCESS_KEY=MinioSecure123 \
            -e AWS_S3_ENDPOINT_URL=http://minio:9000 \
            python:3.11-slim \
            bash -lc "pip install --quiet 'feast[postgres,aws]==0.40.1' pyarrow pandas psycopg2-binary pgvector s3fs && feast apply"

      - name: Build quality outputs
        run: |
          docker run --rm --network mlplatform \
            -v "$PWD:/workspace" \
            -w /workspace \
            python:3.11-slim \
            bash -lc "pip install --quiet pandas trino great-expectations evidently && python quality/generate_quality_assets.py"

      - name: Upload dbt docs
        uses: actions/upload-artifact@v4
        with:
          name: dbt-docs-${{ github.sha }}
          path: dbt/churn_lab/target

      - name: Upload Great Expectations docs
        uses: actions/upload-artifact@v4
        with:
          name: ge-data-docs-${{ github.sha }}
          path: great_expectations/uncommitted/data_docs/local_site

      - name: Upload Evidently report
        uses: actions/upload-artifact@v4
        with:
          name: evidently-report-${{ github.sha }}
          path: evidently/reports

      - name: Log in to GHCR
        if: github.event_name == 'push'
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push MLServer image
        if: github.event_name == 'push'
        uses: docker/build-push-action@v6
        with:
          context: ./mlserver
          push: true
          tags: ${{ env.IMAGE_NAME }}:${{ github.sha }}

  deploy:
    if: github.event_name == 'push'
    needs: validate
    runs-on: [self-hosted]
    steps:
      - uses: actions/checkout@v4

      - name: Copy DAG and generated docs to platform repo
        run: |
          mkdir -p $PLATFORM_ROOT/dbt/churn_lab
          mkdir -p $PLATFORM_ROOT/feast/project
          mkdir -p $PLATFORM_ROOT/training
          mkdir -p $PLATFORM_ROOT/quality
          rsync -a dbt/churn_lab/ $PLATFORM_ROOT/dbt/churn_lab/
          rsync -a feast/project/ $PLATFORM_ROOT/feast/project/
          rsync -a training/ $PLATFORM_ROOT/training/
          rsync -a quality/ $PLATFORM_ROOT/quality/
          cp airflow/dags/churn_workshop_pipeline.py $PLATFORM_ROOT/airflow/dags/churn_workshop_pipeline.py
          rsync -a dbt/churn_lab/target/ $PLATFORM_ROOT/dbt/retail/target/
          rsync -a great_expectations/uncommitted/data_docs/local_site/ $PLATFORM_ROOT/great_expectations/uncommitted/data_docs/local_site/
          rsync -a evidently/reports/ $PLATFORM_ROOT/evidently/reports/

      - name: Write MLServer override file
        run: |
          cat > $PLATFORM_ROOT/docker-compose.override.yml <<EOF
          services:
            mlserver:
              image: ${{ env.IMAGE_NAME }}:${{ github.sha }}
          EOF

      - name: Restart affected services
        run: |
          cd $PLATFORM_ROOT
          docker compose up -d airflow-webserver airflow-scheduler dbt-docs great-expectations-docs evidently-ui mlserver feast

      - name: Verify MLServer health
        run: |
          curl -s http://localhost:8085/v2/docs > /dev/null
          curl -s http://localhost:8085/v2/models/churn-model/infer \
            -H 'Content-Type: application/json' \
            -d '{"inputs":[{"name":"input-0","shape":[1,8],"datatype":"FP64","data":[[28,3,213.96,71.32,15,1,0,0.0]]}]}'
```

### What CI/CD or the platform does next

After merge to `main`, the workflow does exactly this:

1. reruns dbt
2. reruns training
3. reruns Feast apply
4. regenerates quality outputs
5. uploads docs artifacts
6. builds and pushes `ghcr.io/<owner>/<repo>/churn-mlserver:<sha>`
7. copies deployable files into `/srv/ml-platform`
8. restarts Airflow, dbt docs, Great Expectations docs, Evidently, Feast, and MLServer

### How to verify

After your push to `main`:

1. Open the GitHub Actions run and confirm both `validate` and `deploy` are green.
2. Open GHCR and confirm the `churn-mlserver` image has the current commit SHA tag.
3. Open Airflow and confirm `churn_workshop_pipeline` appears in the DAG list.
4. Open dbt docs and search for `customer_360`.
5. Open MLflow and confirm the newest run timestamp is after the workflow start time.

### Common mistakes

- Using a GitHub-hosted runner. That runner cannot reach your local platform.
- Forgetting to create `/srv/ml-platform` on the self-hosted runner host. The deploy job depends on it.
- Building the image but not writing `docker-compose.override.yml`, which means MLServer keeps running the old image.

## 6. Commit, push, and verify every platform surface

### Goal of this section

Move the change through Git and inspect every major platform component after deployment.

### What you will create or change

- your Git history
- your GitHub pull request
- the deployed platform state

### Exact steps

1. Create the branch if you are not already on it:

```bash
git checkout -b workshop/lab1-churn-pipeline
```

2. Stage and commit:

```bash
git add .
git commit -m "lab1: build end-to-end churn pipeline"
git push -u origin workshop/lab1-churn-pipeline
```

3. Open the pull request.
4. Wait for `validate` to finish green.
5. Merge the pull request into `main`.
6. Wait for the `deploy` job to finish green.

### What CI/CD or the platform does next

The workflow pushes the MLServer image, copies the DAG and docs into the platform repo, restarts the affected services, and leaves the data products ready to inspect.

### How to verify

Walk through the platform in this order:

1. CloudBeaver

Run:

```sql
select customer_id, country, total_orders, lifetime_value, churn_label
from iceberg.analytics.customer_360
order by lifetime_value desc
limit 5;
```

Healthy output includes:

- `customer_id = 5` at the top
- `lifetime_value = 319.96`

2. JupyterHub

- open `http://localhost:8888`
- log in
- open `File -> New -> Terminal`
- run `env | egrep 'SPARK_MASTER|TRINO_HOST|MLFLOW_TRACKING_URI|DEMO_POSTGRES_HOST'`

Healthy looks like all four variables are printed.

3. Spark

- open `http://localhost:8080`
- click `Workers`
- confirm one worker is `ALIVE`

4. Trino

- open `http://localhost:8093/v1/info`
- confirm JSON renders

5. MinIO

- open `warehouse/feast/customer_stats/`
- confirm a parquet file exists

6. Airflow

- open `http://localhost:8082`
- confirm DAG `churn_workshop_pipeline` exists

7. Superset

- open `http://localhost:8088`
- click `Settings -> Database Connections -> + Database`
- choose `Trino`
- set SQLAlchemy URI to:

```text
trino://trino@trino:8080/iceberg/analytics
```

- save
- click `Datasets -> + Dataset`
- select the new database and the table `customer_360`
- save
- click `Charts -> + Chart`
- choose `Table`
- choose dataset `customer_360`
- add columns `country`, `lifetime_value`, `churn_label`
- click `Run`

Healthy looks like rows render from the churn mart.

8. Grafana

- open `ML Platform Overview`
- confirm `Prometheus Targets` is not `0`

9. Prometheus

- run `count(up)`
- confirm the result is a positive number

10. Great Expectations

- confirm both validation rows are green

11. Evidently

- confirm the report shows charts and the dataset summary

12. Feast

- open the feature views page
- click `customer_stats`
- confirm it lists `total_orders`, `lifetime_value`, `avg_order_value`, and `days_since_last_order`

13. MLflow

- open experiment `lab1-customer-churn`
- confirm the latest run contains `accuracy` and `f1_score`

14. MLServer

- send the inference request from the foundations document
- confirm a JSON prediction comes back

15. dbt docs

- search for `customer_360`
- open the lineage graph
- confirm upstream staging models connect into it

### Common mistakes

- Looking only at GitHub Actions and never checking the platform UIs. A green pipeline does not prove the runtime looks correct.
- Checking Superset before creating the Trino database connection. Superset does not auto-create it for you in this lab.
