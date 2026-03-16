# Practice Lab 2

## Build the Churn Workflow Directly in `ml-platform`

In this lab, you will build the same customer churn workflow directly inside the `ml-platform` repository. This is simpler than Lab 1 because you do not maintain a separate delivery repo. You still work through Git and CI/CD. You do not patch running containers by hand.

By the end of this lab you will have produced:

- dbt models in this repository
- Feast feature definitions in this repository
- training and quality code in this repository
- an Airflow DAG in this repository
- a GitHub Actions workflow in this repository
- refreshed docs, reports, and a deployed model inside the running platform

## 1. Create your branch and identify the exact files you will own

### Goal of this section

Start the repository-native workflow with a clean branch and a clear list of files you will create or replace.

### What you will create or change

- a Git branch
- the core learner-owned files under `dbt/`, `feast/`, `quality/`, `airflow/`, `mlserver/`, and `.github/workflows/`

### Exact steps

1. From the repository root:

```bash
cd /Users/rohan/Projects/netsol/ml-platform
git checkout -b workshop/lab2-churn-pipeline
mkdir -p training .github/workflows
```

2. Create or replace these files:

```text
dbt/retail/dbt_project.yml
dbt/profiles.yml
dbt/retail/models/sources.yml
dbt/retail/models/staging/stg_customers.sql
dbt/retail/models/staging/stg_orders.sql
dbt/retail/models/staging/stg_order_items.sql
dbt/retail/models/staging/stg_products.sql
dbt/retail/models/staging/stg_events.sql
dbt/retail/models/staging/stg_support_tickets.sql
dbt/retail/models/marts/customer_behavior.sql
dbt/retail/models/marts/product_performance.sql
dbt/retail/models/marts/customer_360.sql
dbt/retail/models/marts/churn_training_dataset.sql
dbt/retail/models/marts/schema.yml
feast/project/feature_store.yaml
feast/project/features.py
quality/generate_quality_assets.py
airflow/dags/churn_workshop_pipeline.py
mlserver/models/churn-model/model-settings.json
.github/workflows/churn_workshop.yml
```

### What CI/CD or the platform does next

Nothing yet. You have only created the branch.

### How to verify

Run:

```bash
git status --short
```

The branch name should be `workshop/lab2-churn-pipeline`.

### Common mistakes

- Editing on `main`.
- Forgetting that Lab 2 still uses Git. This is simpler than Lab 1, not less disciplined.

## 2. Build the dbt project inside this repository

### Goal of this section

Create the transformation layer that the rest of the platform will consume.

### What you will create or change

- the dbt configuration files
- staging SQL
- marts SQL
- schema tests

### Exact steps

1. Replace `dbt/retail/dbt_project.yml` with:

```yaml
name: retail
version: 1.0.0
config-version: 2

profile: retail

model-paths: ["models"]
seed-paths: ["seeds"]
test-paths: ["tests"]
macro-paths: ["macros"]
target-path: "target"
clean-targets: ["target", "dbt_packages"]

models:
  retail:
    staging:
      +materialized: table
    marts:
      +materialized: table

vars:
  lab_snapshot_date: '2024-03-01'
```

2. Replace `dbt/profiles.yml` with:

```yaml
retail:
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

3. Replace `dbt/retail/models/sources.yml` with:

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

4. Replace `dbt/retail/models/staging/stg_customers.sql` with:

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

5. Replace `dbt/retail/models/staging/stg_orders.sql` with:

```sql
select
  order_id,
  customer_id,
  cast(order_date as timestamp) as order_date,
  status,
  cast(total_amount as double) as total_amount
from {{ source('retail_raw', 'orders') }}
```

6. Replace `dbt/retail/models/staging/stg_order_items.sql` with:

```sql
select
  item_id,
  order_id,
  product_id,
  quantity,
  cast(unit_price as double) as unit_price
from {{ source('retail_raw', 'order_items') }}
```

7. Replace `dbt/retail/models/staging/stg_products.sql` with:

```sql
select
  product_id,
  name,
  category,
  cast(unit_price as double) as unit_price,
  stock_qty
from {{ source('retail_raw', 'products') }}
```

8. Replace `dbt/retail/models/staging/stg_events.sql` with:

```sql
select
  event_id,
  customer_id,
  event_type,
  cast(event_ts as timestamp) as event_ts
from {{ source('retail_raw', 'events') }}
```

9. Replace `dbt/retail/models/staging/stg_support_tickets.sql` with:

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

10. Replace `dbt/retail/models/marts/customer_behavior.sql` with:

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

11. Replace `dbt/retail/models/marts/product_performance.sql` with:

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

12. Replace `dbt/retail/models/marts/customer_360.sql` with:

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

13. Replace `dbt/retail/models/marts/churn_training_dataset.sql` with:

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

14. Replace `dbt/retail/models/marts/schema.yml` with:

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

15. Run dbt from the platform repo root:

```bash
docker compose run --rm dbt bash -lc "dbt deps --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && dbt run --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && dbt test --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && dbt docs generate --project-dir /opt/dbt/retail --profiles-dir /opt/dbt"
```

### What CI/CD or the platform does next

Later, the workflow will run this exact command on each pull request and again on deployment pushes to `main`.

### How to verify

1. Open `http://localhost:8090`.
2. Search for `customer_360`.
3. Open the lineage graph.
4. Confirm upstream models include `stg_customers`, `stg_orders`, `stg_support_tickets`, and `customer_behavior`.
5. In CloudBeaver, using the Trino connection, run:

```sql
select count(*) from iceberg.analytics.customer_360;
select count(*) from iceberg.analytics.churn_training_dataset;
select churn_label, count(*) from iceberg.analytics.churn_training_dataset group by 1 order by 1;
```

Expected output:

- `15` rows in `customer_360`
- `15` rows in `churn_training_dataset`
- `8` records with `churn_label = 0`
- `7` records with `churn_label = 1`

### Common mistakes

- Leaving old SQL that still points to `iceberg.retail_raw`. In this lab you are building directly from PostgreSQL.
- Forgetting `dbt docs generate`. If you skip it, the docs page shows stale lineage.

## 3. Create Feast, training, MLServer, and quality code

### Goal of this section

Create the machine-learning layer that consumes the dbt outputs and exposes them through Feast, MLflow, MLServer, Great Expectations, and Evidently.

### What you will create or change

- `feast/project/feature_store.yaml`
- `feast/project/features.py`
- `bootstrap/seed_demo.py` is not used for learner logic in this lab
- `quality/generate_quality_assets.py`
- `training/train_churn_model.py` as a new file
- `mlserver/models/churn-model/model-settings.json`

### Exact steps

1. Create `training/train_churn_model.py`:

```python
from __future__ import annotations

import json
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
S3_ENDPOINT = "http://minio:9000"


def trino_query(sql: str) -> pd.DataFrame:
    conn = trino.dbapi.connect(host="trino", port=8080, user="trino", catalog="iceberg", schema="analytics")
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=[d[0] for d in cur.description])


def s3_filesystem() -> pa_fs.S3FileSystem:
    parsed = urlparse(S3_ENDPOINT)
    return pa_fs.S3FileSystem(
        access_key="mlplatform",
        secret_key="MinioSecure123",
        region="us-east-1",
        scheme=parsed.scheme,
        endpoint_override=parsed.netloc,
    )


def write_parquet(df: pd.DataFrame, uri: str) -> None:
    parsed = urlparse(uri)
    fs = s3_filesystem()
    dataset_path = f"{parsed.netloc}/{parsed.path.lstrip('/').rstrip('/')}"
    fs.delete_dir_contents(dataset_path, missing_dir_ok=True)
    fs.create_dir(dataset_path, recursive=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    with fs.open_output_stream(f"{dataset_path}/part-00000.parquet") as sink:
        pq.write_table(table, sink)


def main() -> None:
    customer_360 = trino_query("select * from iceberg.analytics.customer_360 order by customer_id")
    training_df = trino_query("select * from iceberg.analytics.churn_training_dataset order by customer_id")

    write_parquet(
        customer_360[["customer_id", "total_orders", "lifetime_value", "avg_order_value", "days_since_last_order", "event_timestamp"]],
        "s3://warehouse/feast/customer_stats/",
    )
    write_parquet(
        customer_360[["customer_id", "page_views_30d", "support_tickets", "return_rate", "event_timestamp"]],
        "s3://warehouse/feast/customer_behavior/",
    )

    features = [
        "age",
        "total_orders",
        "lifetime_value",
        "avg_order_value",
        "days_since_last_order",
        "page_views_30d",
        "support_tickets",
        "return_rate",
    ]

    X = training_df[features]
    y = training_df["churn_label"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)

    model = RandomForestClassifier(n_estimators=50, random_state=42)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    mlflow.set_tracking_uri("http://mlflow:5000")
    mlflow.set_experiment("lab2-customer-churn")
    with mlflow.start_run(run_name="lab2-random-forest"):
        mlflow.log_params({"model_type": "RandomForestClassifier", "n_estimators": 50})
        mlflow.log_metrics(
            {
                "accuracy": float(accuracy_score(y_test, preds)),
                "f1_score": float(f1_score(y_test, preds)),
            }
        )

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

2. Replace `feast/project/feature_store.yaml` with:

```yaml
project: retail_features
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

3. Replace `feast/project/features.py` with:

```python
import os
from datetime import timedelta

from feast import Entity, FeatureView, Field, FileSource, ValueType
from feast.data_format import ParquetFormat
from feast.types import Float64, Int64


S3_ENDPOINT = os.getenv("AWS_S3_ENDPOINT_URL", "http://minio:9000")

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

4. Replace `quality/generate_quality_assets.py` with:

```python
from __future__ import annotations

from pathlib import Path

import pandas as pd
import trino
from evidently.metric_preset import DataDriftPreset, DataQualityPreset
from evidently.report import Report
from great_expectations.data_context import FileDataContext


ROOT = Path("/workspace")
GE_ROOT = ROOT / "great_expectations"
GE_DATA = GE_ROOT / "data"
EVIDENTLY_REPORTS = ROOT / "evidently" / "reports"


def trino_query(sql: str) -> pd.DataFrame:
    conn = trino.dbapi.connect(host="trino", port=8080, user="trino", catalog="iceberg", schema="analytics")
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
    datasource = context.sources.add_or_update_pandas_filesystem(name="retail_files", base_directory=str(GE_DATA))
    customer_asset = datasource.add_csv_asset(name="customer_360", batching_regex=r"customer_360\.csv")
    churn_asset = datasource.add_csv_asset(name="churn_training_dataset", batching_regex=r"churn_training_dataset\.csv")

    suites = {
        "customer_360_suite": customer_asset.build_batch_request(),
        "churn_training_suite": churn_asset.build_batch_request(),
    }

    for suite_name, batch_request in suites.items():
        suite = context.add_or_update_expectation_suite(expectation_suite_name=suite_name)
        validator = context.get_validator(batch_request=batch_request, expectation_suite_name=suite.expectation_suite_name)
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
            validations=[{"batch_request": batch_request, "expectation_suite_name": suite.expectation_suite_name}],
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

5. Replace `mlserver/models/churn-model/model-settings.json` with:

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

6. Run the training script:

```bash
docker compose run --rm platform-bootstrap python /workspace/training/train_churn_model.py
```

7. Apply Feast:

```bash
docker compose run --rm feast-bootstrap sh -lc "cd /opt/feast/project && feast apply && feast materialize-incremental $(date -u +%Y-%m-%dT%H:%M:%S)"
```

8. Refresh quality outputs:

```bash
docker compose run --rm quality-bootstrap python /workspace/quality/generate_quality_assets.py
```

### What CI/CD or the platform does next

The workflow later reruns all three commands. Because you are working in the platform repo itself, the deploy step only needs to rebuild or restart the affected services.

### How to verify

1. Open MinIO Console and confirm parquet files exist in:

- `warehouse/feast/customer_stats/`
- `warehouse/feast/customer_behavior/`

2. Open Feast UI and confirm `customer_stats` and `customer_behavior` exist.
3. Open MLflow and confirm experiment `lab2-customer-churn` exists.
4. Open MLServer docs and confirm `churn-model` is available.
5. Open Great Expectations and confirm both suites are green.
6. Open Evidently and confirm the report renders.

### Common mistakes

- Running the quality job before the training script. The quality job expects the churn dataset to exist.
- Forgetting `feast materialize-incremental`. Without materialization, the UI may show feature views but online reads stay empty.

## 4. Create the Airflow DAG and CI/CD workflow

### Goal of this section

Make the platform rerunnable through Airflow and GitHub Actions.

### What you will create or change

- `airflow/dags/churn_workshop_pipeline.py`
- `.github/workflows/churn_workshop.yml`

### Exact steps

1. Create `airflow/dags/churn_workshop_pipeline.py`:

```python
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    "owner": "ml-platform",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="churn_workshop_pipeline",
    default_args=default_args,
    description="Build churn dataset, train model, refresh quality outputs",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    tags=["workshop", "churn"],
) as dag:
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command="dbt deps --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && dbt run --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && dbt test --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && dbt docs generate --project-dir /opt/dbt/retail --profiles-dir /opt/dbt",
    )

    train_model = BashOperator(
        task_id="train_model",
        bash_command="python /opt/platform/training/train_churn_model.py",
    )

    apply_feast = BashOperator(
        task_id="apply_feast",
        bash_command="cd /opt/feast/project && feast apply && feast materialize-incremental $(date -u +%Y-%m-%dT%H:%M:%S)",
    )

    quality = BashOperator(
        task_id="quality",
        bash_command="python /opt/platform/quality/generate_quality_assets.py",
    )

    dbt_build >> train_model >> apply_feast >> quality
```

2. Create `.github/workflows/churn_workshop.yml`:

```yaml
name: churn-workshop

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  validate:
    runs-on: [self-hosted]
    steps:
      - uses: actions/checkout@v4

      - name: dbt build
        run: |
          docker compose run --rm dbt bash -lc "dbt deps --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && dbt run --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && dbt test --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && dbt docs generate --project-dir /opt/dbt/retail --profiles-dir /opt/dbt"

      - name: train model
        run: |
          docker compose run --rm platform-bootstrap python /workspace/training/train_churn_model.py

      - name: feast apply
        run: |
          docker compose run --rm feast-bootstrap sh -lc "cd /opt/feast/project && feast apply && feast materialize-incremental $(date -u +%Y-%m-%dT%H:%M:%S)"

      - name: quality outputs
        run: |
          docker compose run --rm quality-bootstrap python /workspace/quality/generate_quality_assets.py

      - name: upload dbt docs
        uses: actions/upload-artifact@v4
        with:
          name: dbt-docs-${{ github.sha }}
          path: dbt/retail/target

      - name: upload ge docs
        uses: actions/upload-artifact@v4
        with:
          name: ge-data-docs-${{ github.sha }}
          path: great_expectations/uncommitted/data_docs/local_site

      - name: upload evidently
        uses: actions/upload-artifact@v4
        with:
          name: evidently-report-${{ github.sha }}
          path: evidently/reports

  deploy:
    if: github.event_name == 'push'
    needs: validate
    runs-on: [self-hosted]
    steps:
      - uses: actions/checkout@v4

      - name: rebuild changed services
        run: |
          docker compose build dbt feast mlserver quality airflow

      - name: restart changed services
        run: |
          docker compose up -d airflow-webserver airflow-scheduler dbt-docs great-expectations-docs evidently-ui feast mlserver

      - name: verify airflow dag
        run: |
          curl -s -u admin:${{ secrets.AIRFLOW_ADMIN_PASSWORD }} http://localhost:8082/api/v1/dags
```

### What CI/CD or the platform does next

On merge to `main`, CI rebuilds the affected services and restarts them from this repository checkout.

### How to verify

1. Open GitHub Actions and confirm both jobs are green.
2. Open Airflow and confirm `churn_workshop_pipeline` exists.
3. Open dbt docs and confirm the docs page loads.
4. Open Feast UI and confirm the feature views still exist after restart.

### Common mistakes

- Restarting services locally before the pull request has passed. Use the workflow as the source of truth.
- Forgetting to rebuild `mlserver` after changing the model bundle.

## 5. Commit, push, and verify every service

### Goal of this section

Push the repository-native implementation through CI/CD and inspect the result across the platform.

### What you will create or change

- your commit history
- the platform runtime after deploy

### Exact steps

1. Commit and push:

```bash
git add dbt feast quality training airflow mlserver .github/workflows
git commit -m "lab2: build repository-native churn workflow"
git push -u origin workshop/lab2-churn-pipeline
```

2. Open the pull request.
3. Wait for `validate` to finish.
4. Merge to `main`.
5. Wait for `deploy` to finish.

### What CI/CD or the platform does next

The workflow reruns dbt, training, Feast, and quality generation. It rebuilds the affected services and restarts them from this repository.

### How to verify

Use this exact order:

1. CloudBeaver

Run:

```sql
select customer_id, country, total_orders, lifetime_value, churn_label
from iceberg.analytics.customer_360
order by lifetime_value desc
limit 5;
```

2. JupyterHub

- log in
- create a terminal
- run `python -c "import os; print(os.environ['SPARK_MASTER']); print(os.environ['TRINO_HOST']); print(os.environ['MLFLOW_TRACKING_URI'])"`

3. Spark

- open `http://localhost:8080`
- click `Workers`
- confirm the worker is still `ALIVE`

4. Trino

- open `http://localhost:8093/v1/info`
- confirm JSON renders

5. MinIO

- confirm `warehouse/feast/customer_stats/` contains parquet output

6. Airflow

- confirm the DAG list contains `churn_workshop_pipeline`

7. Superset

- if you have not already created a Trino database connection, create one with:

```text
trino://trino@trino:8080/iceberg/analytics
```

- create a dataset from `customer_360`
- create a table chart
- click `Run`

8. Grafana

- open `ML Platform Overview`
- check that `Prometheus Targets` is greater than `0`

9. Prometheus

- run `count(up)`
- confirm the query returns data

10. Great Expectations

- confirm `customer_360_suite` and `churn_training_suite` are green

11. Evidently

- confirm the report renders and is not blank

12. Feast

- confirm `customer_stats` and `customer_behavior` exist

13. MLflow

- confirm experiment `lab2-customer-churn` exists
- open the newest run
- confirm `accuracy` and `f1_score` are populated

14. MLServer

- send the inference request from the foundations document
- confirm a JSON prediction is returned

15. dbt docs

- search for `customer_360`
- confirm the lineage graph is visible

### Common mistakes

- Looking only at local files and never opening the platform UIs.
- Forgetting to re-run Feast after training writes new parquet files.
