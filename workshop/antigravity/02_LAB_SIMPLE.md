# Lab 2 — Repository-Native Pipeline

## What You Are Building

In this lab, you will build a customer churn pipeline that works directly within the `ml-platform` monorepo. Instead of creating everything from scratch like Lab 1, you will leverage the existing repository structure and bootstrap utilities — but you still write every file yourself.

You will:

1. Explore the source database from JupyterHub
2. Ingest data with Airbyte (already set up in the shared foundations step)
3. Write dbt staging and mart models in the repo's `dbt/retail/` directory
4. Run dbt from the dbt container
5. Use the bootstrap script to run PySpark feature engineering and train a PySpark MLlib churn model
6. Define Feast features in the repo's `feast/project/` directory
7. Verify results across all platform UIs

**Prerequisites**: A running platform (see [00_SHARED_FOUNDATIONS.md](00_SHARED_FOUNDATIONS.md)) with Airbyte configured and a sync completed. The only pre-provided data source is the Postgres demo database.

**Key difference from Lab 1**: Lab 1 has you write all PySpark and MLlib code manually. This lab uses the existing `seed_demo.py` bootstrap script for PySpark feature engineering and training, so you focus on dbt models, Feast definitions, and verification.

**End result**: A fully working pipeline with dbt models, Feast features, an MLflow experiment (PySpark MLlib model), a served model, quality reports, and Airflow orchestration — all built by you inside the monorepo.

---

## Section 1 — Explore Source Data from JupyterHub

### Goal

Query the demo PostgreSQL database from a JupyterHub notebook to understand the data you will transform.

### What you will create

A notebook called `explore_source.ipynb`.

### Steps

1. Open `http://localhost:8888` and log in (username `admin`, password from `JUPYTERHUB_ADMIN_PASSWORD` in `.env`).

2. Create a new notebook: **File → New → Notebook** → Python 3 kernel. Name it `explore_source.ipynb`.

3. In the first cell, paste and run:

```python
import os
import pandas as pd
import trino

# Connect to demo-postgres through Trino's postgresql catalog
conn = trino.dbapi.connect(
    host=os.environ.get("TRINO_HOST", "trino"),
    port=int(os.environ.get("TRINO_PORT", "8080")),
    user="trino",
    catalog="postgresql",
    schema="public",
)
cursor = conn.cursor()

# List all tables in the source database
cursor.execute("SHOW TABLES FROM postgresql.public")
tables = pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
print("Source tables in demo-postgres:")
print(tables)
```

4. Expected output — you should see 8 tables listed (customers, products, orders, order_items, events, payments, shipments, support_tickets).

5. In the next cell, explore the customers table:

```python
cursor.execute("""
    SELECT customer_id, first_name, last_name, country, age, is_premium
    FROM postgresql.public.customers
    ORDER BY customer_id
""")
customers = pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
print(f"Total customers: {len(customers)}")
customers
```

6. You should see 15 customers with countries, ages, and premium flags.

7. Explore orders:

```python
cursor.execute("""
    SELECT status, COUNT(*) AS count, SUM(total_amount) AS total
    FROM postgresql.public.orders
    GROUP BY status
""")
pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
```

You should see 3 statuses: `completed`, `returned`, `pending`.

### How to verify

You can query all 8 source tables through Trino's `postgresql` catalog. This confirms the source database is accessible.

---

## Section 2 — Ingest Raw Data with Airbyte

### Goal

Use Airbyte to sync all 8 source tables from PostgreSQL into the Iceberg lakehouse. Airbyte handles this in the production-grade way — incremental syncs, schema evolution, retry logic — without any hand-rolled ingestion code.

### What happens

Airbyte reads from `demo-postgres` and writes to the Iceberg raw layer (`iceberg.retail_raw.*`) in MinIO. This replaces the old bootstrap `ingest_raw` step.

### Steps

1. Open Airbyte at `http://localhost:8000` and log in.

2. Click **"Connections"** → your `demo-postgres → iceberg-minio` connection.

3. Click **"Sync now"** and wait for all 8 tables to show **"Succeeded"**.

If you have not set up Airbyte yet, follow [AIRBYTE_SETUP.md](AIRBYTE_SETUP.md) first.

### How to verify — Trino

In your JupyterHub notebook:

```python
cursor_iceberg = trino.dbapi.connect(
    host="trino", port=8080, user="trino",
    catalog="iceberg", schema="retail_raw",
).cursor()
cursor_iceberg.execute("SHOW TABLES FROM iceberg.retail_raw")
tables = pd.DataFrame(cursor_iceberg.fetchall(), columns=[c[0] for c in cursor_iceberg.description])
print(f"Raw tables: {len(tables)}")
print(tables)
```

You should see 8 tables.

### How to verify — MinIO

1. Open `http://localhost:9001` and log in.
2. Navigate to **warehouse** bucket.
3. Look for `retail_raw/` subfolder containing table directories with `.parquet` files.

---

## Section 3 — Create dbt Staging Models

### Goal

Write the dbt staging models that clean and cast the raw Iceberg tables.

### What you will create

8 SQL files in `dbt/retail/models/staging/` and a `sources.yml` file.

### Steps

**Step 3.1 — Create `dbt/retail/models/sources.yml`**

```yaml
version: 2

sources:
  - name: retail_raw
    database: iceberg
    schema: retail_raw
    tables:
      - name: customers
      - name: products
      - name: orders
      - name: order_items
      - name: events
      - name: payments
      - name: shipments
      - name: support_tickets
```

**Step 3.2 — Create staging model files**

Create each file in `dbt/retail/models/staging/`:

**`stg_customers.sql`**

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

**`stg_products.sql`**

```sql
select
  product_id,
  name,
  category,
  cast(unit_price as double) as unit_price,
  stock_qty
from {{ source('retail_raw', 'products') }}
```

**`stg_orders.sql`**

```sql
select
  order_id,
  customer_id,
  cast(order_date as timestamp) as order_date,
  status,
  cast(total_amount as double) as total_amount
from {{ source('retail_raw', 'orders') }}
```

**`stg_order_items.sql`**

```sql
select
  item_id,
  order_id,
  product_id,
  quantity,
  cast(unit_price as double) as unit_price
from {{ source('retail_raw', 'order_items') }}
```

**`stg_events.sql`**

```sql
select
  event_id,
  customer_id,
  event_type,
  cast(event_ts as timestamp) as event_ts
from {{ source('retail_raw', 'events') }}
```

**`stg_payments.sql`**

```sql
select
  payment_id,
  order_id,
  payment_method,
  payment_status,
  cast(amount as double) as amount,
  cast(paid_at as timestamp) as paid_at
from {{ source('retail_raw', 'payments') }}
```

**`stg_shipments.sql`**

```sql
select
  shipment_id,
  order_id,
  carrier,
  shipment_status,
  cast(shipped_at as timestamp) as shipped_at,
  cast(delivered_at as timestamp) as delivered_at
from {{ source('retail_raw', 'shipments') }}
```

**`stg_support_tickets.sql`**

```sql
select
  ticket_id,
  customer_id,
  priority,
  status,
  issue_type,
  cast(created_at as timestamp) as created_at,
  cast(resolved_at as timestamp) as resolved_at
from {{ source('retail_raw', 'support_tickets') }}
```

**Step 3.3 — Run dbt staging models**

```bash
docker compose exec dbt sh -c "\
  dbt deps --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && \
  dbt run --project-dir /opt/dbt/retail --profiles-dir /opt/dbt --select staging"
```

Expected final line:

```
Done. PASS=8 WARN=0 ERROR=0 SKIP=0 TOTAL=8
```

### Common mistakes

- **File in wrong directory**: Staging models must be in `dbt/retail/models/staging/`, not `dbt/retail/models/`.
- **Missing `sources.yml`**: Without this file, dbt cannot find the `{{ source() }}` references and will fail.

---

## Section 4 — Create dbt Mart Models

### Goal

Build the analytics marts that aggregate staging data into business-ready tables.

### What you will create

4 SQL files in `dbt/retail/models/marts/`.

### Steps

Create each file in `dbt/retail/models/marts/`:

**`customer_behavior.sql`**

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
    current_timestamp as event_timestamp
from events
group by 1
```

**`product_performance.sql`**

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
    current_timestamp as event_timestamp
from products p
left join items i on p.product_id = i.product_id
group by 1, 2, 3, 4, 5
```

**`customer_360.sql`**

```sql
with customers as (
    select * from {{ ref('stg_customers') }}
),
orders as (
    select * from {{ ref('stg_orders') }}
),
payments as (
    select * from {{ ref('stg_payments') }}
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
        date_diff('day', cast(max(order_date) as date), current_date) as days_since_last_order,
        sum(case when status = 'returned' then 1 else 0 end) * 1.0 / nullif(count(*), 0) as return_rate
    from orders
    group by 1
),
payments_agg as (
    select
        o.customer_id,
        count(*) filter (where p.payment_status = 'captured') as successful_payments
    from payments p
    join orders o on p.order_id = o.order_id
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
    coalesce(p.successful_payments, 0) as successful_payments,
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
    current_timestamp as event_timestamp
from customers c
left join orders_agg o on c.customer_id = o.customer_id
left join payments_agg p on c.customer_id = p.customer_id
left join support_agg s on c.customer_id = s.customer_id
left join behavior b on c.customer_id = b.customer_id
```

**`churn_training_dataset.sql`**

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

### Run all models and tests

```bash
docker compose exec dbt sh -c "\
  dbt run --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && \
  dbt test --project-dir /opt/dbt/retail --profiles-dir /opt/dbt"
```

Expected: `PASS=12 WARN=0 ERROR=0 SKIP=0 TOTAL=12`

### Generate dbt docs

```bash
docker compose exec dbt sh -c "\
  dbt docs generate --project-dir /opt/dbt/retail --profiles-dir /opt/dbt --empty-catalog --static"
```

### How to verify — dbt docs site

1. Open `http://localhost:8090`.
2. Browse the model list. Click `customer_360` to see its SQL.
3. Open the lineage graph — confirm staging models feed into marts.

### How to verify — Trino

In JupyterHub:

```python
conn_iceberg = trino.dbapi.connect(
    host="trino", port=8080, user="trino",
    catalog="iceberg", schema="analytics",
)
cursor_iceberg = conn_iceberg.cursor()
cursor_iceberg.execute("SELECT COUNT(*) FROM iceberg.analytics.churn_training_dataset")
count = cursor_iceberg.fetchone()[0]
print(f"Churn training dataset: {count} rows")
```

Expected: `15 rows` (one per customer).

---

## Section 5 — Publish Features, Train Model, and Generate Artifacts

### Goal

Use the bootstrap script to run PySpark feature engineering, train a PySpark MLlib churn model, log it to MLflow, and save the MLServer model bundle.

### What happens

The `post_dbt` step of `seed_demo.py`:
1. Creates a SparkSession connected to the Spark cluster and Iceberg catalog
2. Reads `customer_360`, `customer_behavior`, and `product_performance` from Iceberg via Spark SQL
3. Writes each as Parquet files to MinIO (`s3a://warehouse/feast/...`) using Spark's native writer
4. Reads `churn_training_dataset` from Iceberg and trains a PySpark MLlib `RandomForestClassifier` pipeline
5. Evaluates the model (accuracy + AUC) and logs params, metrics, and the Spark model to MLflow under the `retail-churn-demo` experiment
6. Saves the MLflow Spark model to `mlserver/models/churn-model/mlflow_model/` for MLServer
7. Generates a `scored_dataset.csv` for Evidently

### Steps

```bash
docker compose exec airflow-scheduler bash -c \
  "python /opt/bootstrap/seed_demo.py --step post_dbt"
```

Expected output:

```
[bootstrap] Publishing Feast feature sources via Spark...
[bootstrap]   customer_stats: 15 rows
[bootstrap]   customer_behavior: 14 rows
[bootstrap]   product_stats: 15 rows
[bootstrap] Feast feature sources published.
[bootstrap] Loading churn training dataset from Iceberg...
[bootstrap]   Train: ... rows, Test: ... rows
[bootstrap] Training PySpark MLlib RandomForestClassifier pipeline...
[bootstrap]   Accuracy: ..., AUC: ...
[bootstrap]   MLflow Spark model saved to .../mlflow_model
[bootstrap]   Scored dataset written for Evidently.
[bootstrap] Spark session stopped.
[bootstrap] Post-dbt bootstrap complete.
```

> **Note**: The first run downloads Maven JARs and takes 3–8 minutes. Subsequent runs are faster.

### How to verify — MinIO

1. Open `http://localhost:9001`.
2. Navigate to **warehouse** → **feast**.
3. You should see three folders: `customer_stats/`, `customer_behavior/`, `product_stats/`.
4. Each should contain Parquet files written by Spark.

### How to verify — MLflow

1. Open `http://localhost:5000` and log in.
2. Click the **"retail-churn-demo"** experiment.
3. You should see a run named `bootstrap-pyspark-random-forest`.
4. Click it. Verify:
   - **Parameters**: `model_type = PySpark_RandomForestClassifier`, `num_trees = 50`, `framework = pyspark.ml`
   - **Metrics**: `accuracy` and `auc` (values between 0 and 1)
   - **Tags**: `training_framework = PySpark MLlib`

### How to verify — MLServer model

1. Check that the model directory exists:
   ```bash
   ls -la mlserver/models/churn-model/
   ```
   You should see a `mlflow_model/` directory and `model-settings.json`.

2. If MLServer is running, test it:
   ```bash
   curl -s http://localhost:8085/v2/models/churn-model/infer \
     -H 'Content-Type: application/json' \
     -d '{
       "inputs": [{
         "name": "predict",
         "shape": [1, 8],
         "datatype": "FP64",
         "data": [[28, 3, 164.98, 54.99, 10, 5, 0, 0.0]]
       }]
     }' | python3 -m json.tool
   ```
   You should see a JSON response with a prediction value (`0.0` = not churning, `1.0` = churning).

---

## Section 6 — Define and Apply Feast Features

### Goal

Create the Feast feature store configuration and feature definitions.

### What you will create

Two files in `feast/project/`: `feature_store.yaml` and `features.py`.

### Steps

**File: `feast/project/feature_store.yaml`**

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

**File: `feast/project/features.py`**

```python
import os
from datetime import timedelta
from feast import Entity, FeatureView, Field, FileSource, ValueType
from feast.data_format import ParquetFormat
from feast.types import Float64, Int64, Bool, String

S3_ENDPOINT = os.getenv("AWS_S3_ENDPOINT_URL", "http://minio:9000")

customer = Entity(
    name="customer", join_keys=["customer_id"],
    value_type=ValueType.INT64,
)
product = Entity(
    name="product", join_keys=["product_id"],
    value_type=ValueType.INT64,
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
product_stats_source = FileSource(
    name="product_stats_source",
    path="s3://warehouse/feast/product_stats/",
    file_format=ParquetFormat(),
    timestamp_field="event_timestamp",
    s3_endpoint_override=S3_ENDPOINT,
)

customer_stats = FeatureView(
    name="customer_stats", entities=[customer], ttl=timedelta(days=30),
    schema=[
        Field(name="age", dtype=Int64),
        Field(name="country", dtype=String),
        Field(name="is_premium", dtype=Bool),
        Field(name="total_orders", dtype=Int64),
        Field(name="lifetime_value", dtype=Float64),
        Field(name="days_since_last_order", dtype=Int64),
        Field(name="avg_order_value", dtype=Float64),
    ],
    source=customer_stats_source,
)
customer_behavior = FeatureView(
    name="customer_behavior", entities=[customer], ttl=timedelta(days=14),
    schema=[
        Field(name="page_views_30d", dtype=Int64),
        Field(name="add_to_cart_30d", dtype=Int64),
        Field(name="support_tickets", dtype=Int64),
        Field(name="checkout_rate", dtype=Float64),
    ],
    source=customer_behavior_source,
)
product_stats = FeatureView(
    name="product_stats", entities=[product], ttl=timedelta(days=7),
    schema=[
        Field(name="category", dtype=String),
        Field(name="unit_price", dtype=Float64),
        Field(name="times_ordered", dtype=Int64),
        Field(name="units_sold", dtype=Int64),
        Field(name="revenue", dtype=Float64),
        Field(name="stock_qty", dtype=Int64),
    ],
    source=product_stats_source,
)
```

**Apply the definitions:**

```bash
docker compose exec feast sh -c "feast -c /opt/feast/project apply"
```

Expected output:

```
Created entity customer
Created entity product
Created feature view customer_stats
Created feature view customer_behavior
Created feature view product_stats
```

**Materialize to online store:**

```bash
docker compose exec feast sh -c \
  "feast -c /opt/feast/project materialize-incremental \$(date -u +%Y-%m-%dT%H:%M:%S)"
```

### How to verify — Feast UI

1. Open `http://localhost:6567`.
2. **Feature Views**: 3 listed (customer_stats, customer_behavior, product_stats).
3. **Entities**: 2 listed (customer, product).
4. **Data Sources**: 3 listed pointing to `s3://warehouse/feast/...` paths.

---

## Section 7 — Run Data Quality Checks

### Goal

Generate Great Expectations Data Docs and an Evidently drift report.

### Steps

Run the quality bootstrap script:

```bash
docker compose run --rm quality-bootstrap
```

This script:
1. Queries `customer_360` and `churn_training_dataset` from Trino
2. Saves them as CSV files
3. Creates Great Expectations expectation suites and runs checkpoints
4. Builds GE Data Docs
5. Generates an Evidently drift report from the scored dataset

### How to verify — Great Expectations

1. Open `http://localhost:8091`.
2. You should see validation results for `customer_360_suite` and `churn_training_suite`.
3. Click each. All expectations should show green checkmarks:
   - `customer_id` values are never null ✓
   - `total_orders` values are between 0 and upper bound ✓
   - `churn_label` distinct values are in {0, 1} ✓

### How to verify — Evidently

1. Open `http://localhost:8092`.
2. You should see the drift report with **Data Quality** and **Data Drift** sections.
3. `avg_order_value` should show drift detected (intentionally inflated by 15%).

---

## Section 8 — Verify the Airflow DAG

### Goal

Confirm that the Airflow DAG exists and can run the entire pipeline end-to-end.

### Steps

The DAG file at `airflow/dags/retail_pipeline.py` should already exist. If not, create it with the content from Lab 1, Section 13.

1. Open `http://localhost:8082` and log in.
2. Look for `retail_ml_pipeline` in the DAG list.
3. If paused, click the toggle to unpause.
4. Click **Play** (▶) → **Trigger DAG** to start a manual run.
5. Click the DAG name → **Grid** view.
6. Watch the 4 tasks run: `verify_airbyte_sync` → `dbt_run_and_test` → `publish_features_and_train` → `refresh_docs_index`.
7. All 4 should turn green.

### What each task does

| Task | What it runs | What it produces |
|---|---|---|
| `verify_airbyte_sync` | Python Trino check | Confirms 8 raw tables exist (Airbyte must have synced) |
| `dbt_run_and_test` | `dbt deps && dbt run && dbt test` | Staging + mart tables in `analytics` schema |
| `publish_features_and_train` | `seed_demo.py --step post_dbt` | Feast parquet files (via PySpark), MLflow run, MLServer MLflow Spark model |
| `refresh_docs_index` | checks for seed_manifest.json | Confirms artifacts were created |

### Common mistakes

- **`verify_airbyte_sync` fails immediately**: Airbyte hasn't synced yet. Open `http://localhost:8000` and trigger a manual sync.
- **DAG not appearing**: Airflow scans `airflow/dags/` every ~30 seconds. Wait a minute. If it still does not appear, check `docker compose logs airflow-scheduler` for import errors.
- **`publish_features_and_train` fails**: Most common cause is Spark or MinIO connectivity. Check `docker compose logs airflow-scheduler --tail=100` for the PySpark error.

---

## Section 9 — Verify Superset, Grafana, and Prometheus

### Goal

Complete the end-to-end verification by checking the BI and monitoring tools.

### Steps

**Superset:**

1. Open `http://localhost:8088` and log in.
2. Go to **Settings** → **Database Connections** → **"+ Database"** → select **Trino**.
3. SQLAlchemy URI: `trino://trino@trino:8080/iceberg/analytics`
4. Click **Test Connection** → green success → **Connect**.
5. Go to **SQL Lab** → **SQL Editor**. Select your Trino database.
6. Run:
   ```sql
   SELECT country, COUNT(*) AS customers,
          ROUND(AVG(lifetime_value), 2) AS avg_ltv
   FROM customer_360
   GROUP BY country ORDER BY avg_ltv DESC
   ```
7. You should see results with country, customer count, and average lifetime value.

**Prometheus:**

1. Open `http://localhost:9090`.
2. Click **Status** → **Targets**.
3. Both targets (`prometheus` and `demo_postgres`) should show **UP** (green).
4. In the query box, type `pg_up` → click **Execute**. You should see value `1`.

**Grafana:**

1. Open `http://localhost:3000` and log in.
2. Click **Dashboards** in the left sidebar.
3. Click **"ML Platform Overview"**.
4. You should see panels with PostgreSQL metrics. If any panel shows "No data", check the Prometheus data source: **Settings** → **Data Sources** → **Prometheus** → **Test**.

---

## Section 10 — Verify Spark Cluster Health

### Goal

Confirm the Spark cluster is healthy and available for compute workloads.

### Steps

1. Open `http://localhost:8080` (Spark Master UI).
2. Look for the **Workers** section. It should list **1 worker**.
3. Check the worker's resources:
   - **Cores**: should match `SPARK_WORKER_CORES` from `.env` (default: 4)
   - **Memory**: should match `SPARK_WORKER_MEMORY` from `.env` (default: 8G)
4. Under **Running Applications**: should be empty (no active jobs right now).
5. Under **Completed Applications**: should show the PySpark training job run by the bootstrap script.

6. Open `http://localhost:8081` (Spark Worker UI).
7. Check **Cores Used** vs **Cores Available** — should show `0` used if no job is running.
8. If all cores show as used, another application is consuming resources. Go back to the Master UI and check Running Applications.

---

## Lab Complete

You have now built the entire pipeline within the monorepo:

1. ✅ Explored source data from JupyterHub
2. ✅ Ingested 8 tables into Iceberg using Airbyte
3. ✅ Created 8 dbt staging models and 4 mart models
4. ✅ Ran dbt and generated docs
5. ✅ Used PySpark to publish features to MinIO and trained a PySpark MLlib model
6. ✅ Logged PySpark MLlib model to MLflow, saved MLflow Spark model for MLServer
7. ✅ Defined and applied Feast features
8. ✅ Ran Great Expectations and Evidently quality checks
9. ✅ Verified the Airflow DAG with Airbyte sync verification
10. ✅ Connected Superset to Trino and queried marts
11. ✅ Verified Grafana, Prometheus, and Spark health

All artifacts are stored in the monorepo. Airflow can re-run the entire pipeline daily on schedule.
