# Lab 1 — Production-Style Customer Churn Pipeline

## What You Are Building

In this lab, you will build an end-to-end customer churn prediction pipeline starting from a Postgres demo database. You will:

1. Connect to the source database and explore the raw data
2. Ingest all 8 source tables into the Iceberg lakehouse using Airbyte
3. Build dbt staging and mart models that transform raw data into analytics-ready tables
4. Validate data quality with Great Expectations
5. Use PySpark for distributed feature engineering — read Iceberg marts, compute features, write Parquet for Feast
6. Register and materialize Feast features
7. Train a PySpark MLlib churn model and log it to MLflow
8. Deploy the model to MLServer via the MLflow Spark runtime
9. Generate an Evidently drift report
10. Wire everything into an Airflow DAG for scheduled orchestration
11. Verify results across Grafana, Prometheus, Superset, and all platform UIs

**Prerequisites**: A running platform (see [00_SHARED_FOUNDATIONS.md](00_SHARED_FOUNDATIONS.md)) with Airbyte configured. You need only the Postgres demo database — everything else you will create yourself.

**End result**: A fully working, automated ML pipeline that runs daily via Airflow, with every artifact inspectable through the platform's UIs.

---

## Section 1 — Explore the Source Database with CloudBeaver

### Goal

Connect to the demo PostgreSQL database and understand the tables you will be working with throughout this lab.

### What you will do

- Set up a CloudBeaver connection to `demo-postgres`
- Browse all 8 tables and 3 views
- Understand the data schema

### Steps

1. Open `http://localhost:8978` in your browser.

2. If this is your first visit, CloudBeaver will prompt you to create an admin account. Enter any username and password you want (these are for CloudBeaver only).

3. After logging in, click **"New Connection"** in the top-left toolbar.

4. Select **PostgreSQL** from the driver list.

5. Enter these connection details:
   - **Host**: `demo-postgres`
   - **Port**: `5432`
   - **Database**: `retail_db`
   - **Username**: `analyst`
   - **Password**: `analyst123`

6. Click **"Test Connection"**. You should see a green checkmark.

7. Click **"Create"**.

8. In the left sidebar, expand: your connection → `retail_db` → `public` → `Tables`.

9. You should see these 8 tables:

   | Table | Row Count | Description |
   |---|---|---|
   | `customers` | 15 | Customer profiles with age, country, premium flag |
   | `products` | 15 | Product catalog with categories and prices |
   | `orders` | 20 | Order records with status and totals |
   | `order_items` | 31 | Line items linking orders to products |
   | `events` | 21 | Customer behavioral events (page views, checkouts, etc.) |
   | `payments` | 20 | Payment records with method and status |
   | `shipments` | 20 | Shipping records with carrier and delivery status |
   | `support_tickets` | 7 | Customer support tickets with priority and resolution |

10. Click the `customers` table, then click the **"Data"** tab. Verify you see 15 rows with columns like `customer_id`, `first_name`, `last_name`, `email`, `country`, `age`, `signup_date`, `is_premium`.

11. Also expand `Views` in the sidebar. You should see 3 views: `customer_summary`, `product_performance`, `order_ops_overview`. These are pre-created in the source database for analyst convenience — you will build richer versions in dbt later.

### How to verify

You can see all 8 tables and their data in CloudBeaver. If any table is missing or shows 0 rows, the `demo-postgres` container did not initialize correctly. Fix: run `docker compose -f docker-compose.demo-postgres.yml down && docker compose -f docker-compose.demo-postgres.yml up -d` and wait for the healthcheck.

### Common mistakes

- Using `localhost` instead of `demo-postgres` as the host. CloudBeaver runs inside Docker, so it must use the container name.
- Using port `5433` instead of `5432`. Port `5433` is the host-mapped port; inside Docker the database listens on `5432`.

---

## Section 2 — Ingest Raw Data into Iceberg with Airbyte

### Goal

Use Airbyte to sync all 8 source tables from PostgreSQL into the Iceberg lakehouse. Airbyte handles incremental CDC-capable ingestion, schema evolution, and retry logic — this is the production-grade ingestion layer replacing hand-rolled Spark JDBC scripts.

### What you will create

An Airbyte connection: `demo-postgres` (PostgreSQL source) → `iceberg-minio` (S3 Data Lake / Iceberg destination).

### Steps

If you have not already set up Airbyte, follow [AIRBYTE_SETUP.md](AIRBYTE_SETUP.md) first.

1. Open `http://localhost:8000` and log in (username `airbyte`, password `password`).

2. Click **"Connections"** in the left sidebar.

3. Click your `demo-postgres → iceberg-minio` connection.

4. Click **"Sync now"** to trigger a manual sync.

5. Wait for all 8 tables to show **"Succeeded"** status. This typically takes 1–3 minutes.

### How to verify — Trino

After the sync, verify the raw tables exist in Trino:

1. Open JupyterHub at `http://localhost:8888` and log in.

2. Create a new notebook. In the first cell:

```python
import os
import pandas as pd
import trino

conn = trino.dbapi.connect(
    host=os.environ.get("TRINO_HOST", "trino"),
    port=int(os.environ.get("TRINO_PORT", "8080")),
    user="trino",
    catalog="iceberg",
    schema="retail_raw",
)
cursor = conn.cursor()

cursor.execute("SHOW TABLES FROM iceberg.retail_raw")
tables = pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
print("Tables in iceberg.retail_raw:")
print(tables)
```

3. You should see 8 tables. Verify row counts:

```python
expected_counts = {
    "customers": 15, "products": 15, "orders": 20, "order_items": 31,
    "events": 21, "payments": 20, "shipments": 20, "support_tickets": 7,
}

for table, expected in expected_counts.items():
    cursor.execute(f"SELECT COUNT(*) AS cnt FROM iceberg.retail_raw.{table}")
    actual = cursor.fetchone()[0]
    status = "✓" if actual == expected else "✗"
    print(f"{status} {table}: {actual} rows (expected {expected})")
```

### How to verify — MinIO

1. Open `http://localhost:9001` and log in.
2. Click **Object Browser** → **warehouse** bucket.
3. Navigate into the `retail_raw/` folder. You should see subfolders for each table with `.parquet` files.

### Common mistakes

- **Connection refused when setting up Airbyte source**: The PostgreSQL source must use `host.docker.internal` as the host (not `demo-postgres`) because Airbyte runs in its own Kubernetes cluster. Port must be `5433` (the host-mapped port).
- **Tables not appearing in Trino after sync**: If Airbyte used Parquet output instead of native Iceberg, you may need to register the tables. See the notes in [AIRBYTE_SETUP.md](AIRBYTE_SETUP.md).

---

## Section 3 — Verify the Raw Layer in Trino

### Goal

Confirm that Trino can see the Iceberg tables Airbyte created, and query them with SQL.

### Steps

Continue in your JupyterHub notebook from Section 2. Verify schema:

```python
cursor.execute("SHOW SCHEMAS FROM iceberg")
schemas = pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
print(schemas)
```

Expected: `analytics`, `information_schema`, `retail_raw`.

Query a sample:

```python
cursor.execute("SELECT customer_id, first_name, country, age FROM iceberg.retail_raw.customers LIMIT 5")
df = pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
print(df)
```

### How to verify — Trino Web UI

1. Open `http://localhost:8093`.
2. Look at **"Finished Queries"** — you should see your recent queries listed.
3. Click any query to see its execution details.

---

## Section 4 — Verify Raw Data in MinIO

### Goal

Visually confirm that the Iceberg parquet files are stored in MinIO.

### Steps

1. Open `http://localhost:9001` and log in.
2. Click **Object Browser** in the left sidebar.
3. Click the **warehouse** bucket.
4. Navigate to find `retail_raw/` (may be nested under the Iceberg catalog structure).
5. Click into any table folder (e.g., `customers`) and drill down until you see `.parquet` files.
6. The presence of `.parquet` files confirms Airbyte successfully wrote the data.

---

## Section 5 — Build dbt Staging Models

### Goal

Create dbt staging models that read from the Iceberg raw tables and clean/cast the data. These models run through Trino and write back to Iceberg.

### What you will create

8 SQL files in `dbt/retail/models/staging/` plus a `sources.yml` file and dbt configuration files.

### Steps

**Step 5.1 — Verify dbt configuration files exist**

These files should already exist in the repository. Verify them:

1. Open the file `dbt/profiles.yml` in your editor. It should contain:

```yaml
ml_platform:
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

2. Open `dbt/retail/dbt_project.yml`. It should contain:

```yaml
name: retail
version: "1.0.0"
config-version: 2

profile: ml_platform

model-paths: ["models"]
analysis-paths: ["analyses"]
test-paths: ["tests"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
snapshot-paths: ["snapshots"]
clean-targets: ["target", "dbt_packages"]

models:
  retail:
    staging:
      +materialized: table
    marts:
      +materialized: table
flags:
  require_generic_test_arguments_property: true
```

**Step 5.2 — Create the sources file**

Create the file `dbt/retail/models/sources.yml` with this content:

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

This tells dbt where to find the raw Iceberg tables created by Airbyte.

**Step 5.3 — Create all 8 staging models**

Create each file below in `dbt/retail/models/staging/`.

**File: `dbt/retail/models/staging/stg_customers.sql`**

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

**File: `dbt/retail/models/staging/stg_products.sql`**

```sql
select
  product_id,
  name,
  category,
  cast(unit_price as double) as unit_price,
  stock_qty
from {{ source('retail_raw', 'products') }}
```

**File: `dbt/retail/models/staging/stg_orders.sql`**

```sql
select
  order_id,
  customer_id,
  cast(order_date as timestamp) as order_date,
  status,
  cast(total_amount as double) as total_amount
from {{ source('retail_raw', 'orders') }}
```

**File: `dbt/retail/models/staging/stg_order_items.sql`**

```sql
select
  item_id,
  order_id,
  product_id,
  quantity,
  cast(unit_price as double) as unit_price
from {{ source('retail_raw', 'order_items') }}
```

**File: `dbt/retail/models/staging/stg_events.sql`**

```sql
select
  event_id,
  customer_id,
  event_type,
  cast(event_ts as timestamp) as event_ts
from {{ source('retail_raw', 'events') }}
```

**File: `dbt/retail/models/staging/stg_payments.sql`**

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

**File: `dbt/retail/models/staging/stg_shipments.sql`**

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

**File: `dbt/retail/models/staging/stg_support_tickets.sql`**

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

**Step 5.4 — Run dbt staging models**

Run the dbt commands from inside the `dbt` container:

```bash
docker compose exec dbt sh -c "\
  dbt deps --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && \
  dbt run --project-dir /opt/dbt/retail --profiles-dir /opt/dbt --select staging"
```

Expected output (last lines):

```
Completed successfully

Done. PASS=8 WARN=0 ERROR=0 SKIP=0 TOTAL=8
```

**Step 5.5 — Verify staging models in Trino**

Go back to your JupyterHub notebook and run:

```python
cursor.execute("SHOW TABLES FROM iceberg.analytics")
tables = pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
print(tables)
```

You should see at least 8 staging tables (`stg_customers`, `stg_products`, etc.) listed under the `analytics` schema.

### Common mistakes

- **Wrong source name**: If you misspell `retail_raw` in `sources.yml` vs. the `{{ source() }}` calls, dbt will fail with `Source retail_raw not found`.
- **Cast errors**: Trino Iceberg types are strict. If you forget `cast(... as double)` on numeric columns, you may get type mismatch errors.

---

## Section 6 — Build dbt Mart Models

### Goal

Create the analytics mart models that aggregate raw data into business-ready tables: customer 360 view, customer behavior, product performance, and a churn training dataset.

### What you will create

4 SQL files in `dbt/retail/models/marts/`.

### Steps

**File: `dbt/retail/models/marts/customer_behavior.sql`**

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

**File: `dbt/retail/models/marts/product_performance.sql`**

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

**File: `dbt/retail/models/marts/customer_360.sql`**

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

**File: `dbt/retail/models/marts/churn_training_dataset.sql`**

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

**Run all dbt models:**

```bash
docker compose exec dbt sh -c "\
  dbt run --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && \
  dbt test --project-dir /opt/dbt/retail --profiles-dir /opt/dbt"
```

Expected output (last lines):

```
Completed successfully

Done. PASS=12 WARN=0 ERROR=0 SKIP=0 TOTAL=12
```

(8 staging + 4 mart models = 12 total)

**Generate dbt docs:**

```bash
docker compose exec dbt sh -c "\
  dbt docs generate --project-dir /opt/dbt/retail --profiles-dir /opt/dbt --empty-catalog --static"
```

### How to verify — dbt docs site

1. Open `http://localhost:8090` in your browser.
2. You should see the dbt documentation homepage listing all 12 models.
3. Click `customer_360` to see its SQL and column descriptions.
4. Click the **lineage graph** icon. You should see the DAG: staging models feeding into `customer_behavior` → `customer_360` → `churn_training_dataset`.

### How to verify — Trino

In JupyterHub:

```python
cursor.execute("""
    SELECT customer_id, age, total_orders, lifetime_value,
           churn_label
    FROM iceberg.analytics.churn_training_dataset
    ORDER BY customer_id
""")
df = pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
print(f"Rows: {len(df)}")
print(df.head(10))
```

You should see 15 rows (one per customer) with computed features and churn labels.

---

## Section 7 — Validate Data with Great Expectations

### Goal

Run data quality checks against the dbt mart outputs and generate an HTML validation report.

### Steps

1. In JupyterHub, create a new notebook called `validate_quality.ipynb`.

2. In the first cell:

```python
import os
from pathlib import Path

import pandas as pd
import trino
from great_expectations.data_context import FileDataContext

conn = trino.dbapi.connect(
    host=os.environ.get("TRINO_HOST", "trino"),
    port=int(os.environ.get("TRINO_PORT", "8080")),
    user="trino", catalog="iceberg", schema="analytics",
)
cursor = conn.cursor()

cursor.execute("SELECT * FROM iceberg.analytics.customer_360")
customer_360 = pd.DataFrame(cursor.fetchall(),
                            columns=[c[0] for c in cursor.description])

cursor.execute("SELECT * FROM iceberg.analytics.churn_training_dataset")
churn_training = pd.DataFrame(cursor.fetchall(),
                              columns=[c[0] for c in cursor.description])

GE_ROOT = Path("/srv/jupyterhub/great_expectations")
GE_DATA = GE_ROOT / "data"
GE_DATA.mkdir(parents=True, exist_ok=True)

customer_360.to_csv(GE_DATA / "customer_360.csv", index=False)
churn_training.to_csv(GE_DATA / "churn_training_dataset.csv", index=False)
print(f"Exported {len(customer_360)} customer_360 rows")
print(f"Exported {len(churn_training)} churn_training rows")
```

3. In the second cell:

```python
context = FileDataContext.create(project_root_dir=str(GE_ROOT))

datasource = context.sources.add_or_update_pandas_filesystem(
    name="retail_files", base_directory=str(GE_DATA),
)
customer_asset = datasource.add_csv_asset(
    name="customer_360", batching_regex=r"customer_360\.csv",
)
churn_asset = datasource.add_csv_asset(
    name="churn_training_dataset",
    batching_regex=r"churn_training_dataset\.csv",
)

suites = {
    "customer_360_suite": customer_asset.build_batch_request(),
    "churn_training_suite": churn_asset.build_batch_request(),
}

for suite_name, batch_request in suites.items():
    suite = context.add_or_update_expectation_suite(
        expectation_suite_name=suite_name,
    )
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
        validations=[{
            "batch_request": batch_request,
            "expectation_suite_name": suite.expectation_suite_name,
        }],
    )
    result = context.run_checkpoint(checkpoint_name=f"{suite_name}_checkpoint")
    print(f"{suite_name}: {'PASSED' if result.success else 'FAILED'}")

context.build_data_docs()
print("Great Expectations Data Docs generated.")
```

### How to verify

1. Open `http://localhost:8091` in your browser.
2. You should see the Data Docs homepage with two validation results.
3. Each expectation should have a green checkmark (passed).

---

## Section 8 — Spark Feature Engineering

### Goal

Use PySpark to read the dbt analytics marts from Iceberg, compute features, and write Parquet files for Feast. This demonstrates Spark's role in the platform: distributed compute for feature engineering that goes beyond what SQL can do.

### What you will create

A notebook `spark_feature_engineering.ipynb` that reads Iceberg marts with Spark and writes feature Parquet files to MinIO.

### Steps

1. In JupyterHub, create a new notebook called `spark_feature_engineering.ipynb`.

2. In the first cell, create the Spark session:

```python
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, log1p

PACKAGES = ",".join([
    "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2",
    "org.apache.iceberg:iceberg-aws-bundle:1.5.2",
    "software.amazon.awssdk:url-connection-client:2.25.53",
    "org.apache.hadoop:hadoop-aws:3.3.4",
    "com.amazonaws:aws-java-sdk-bundle:1.12.262",
    "org.postgresql:postgresql:42.7.3",
])

aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "mlplatform")
aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "MinioSecure123")
aws_region     = os.environ.get("AWS_REGION", "us-east-1")
spark_master   = os.environ.get("SPARK_MASTER", "spark://spark-master:7077")
s3_endpoint    = os.environ.get("AWS_S3_ENDPOINT", "http://minio:9000")
iceberg_uri    = os.environ.get("ICEBERG_JDBC_URI", "jdbc:postgresql://postgres-iceberg:5432/iceberg_catalog")

spark = (
    SparkSession.builder
    .appName("Lab1-FeatureEngineering")
    .master(spark_master)
    .config("spark.jars.packages", PACKAGES)
    .config("spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
    .config("spark.sql.catalog.warehouse", "org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.warehouse.type", "jdbc")
    .config("spark.sql.catalog.warehouse.uri", iceberg_uri)
    .config("spark.sql.catalog.warehouse.jdbc.user",
            os.environ.get("ICEBERG_JDBC_USER", "iceberg"))
    .config("spark.sql.catalog.warehouse.jdbc.password",
            os.environ.get("ICEBERG_JDBC_PASSWORD", "iceberg123"))
    .config("spark.sql.catalog.warehouse.jdbc.schema-version", "V1")
    .config("spark.sql.catalog.warehouse.warehouse", "s3://warehouse/")
    .config("spark.sql.catalog.warehouse.io-impl",
            "org.apache.iceberg.aws.s3.S3FileIO")
    .config("spark.sql.catalog.warehouse.http-client.type", "urlconnection")
    .config("spark.sql.catalog.warehouse.client.region", aws_region)
    .config("spark.sql.catalog.warehouse.s3.endpoint", s3_endpoint)
    .config("spark.sql.catalog.warehouse.s3.path-style-access", "true")
    .config("spark.sql.catalog.warehouse.s3.access-key-id", aws_access_key)
    .config("spark.sql.catalog.warehouse.s3.secret-access-key", aws_secret_key)
    .config("spark.hadoop.fs.s3a.endpoint", s3_endpoint)
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .config("spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
    .config("spark.hadoop.fs.s3a.access.key", aws_access_key)
    .config("spark.hadoop.fs.s3a.secret.key", aws_secret_key)
    .getOrCreate()
)

print(f"Spark {spark.version} connected to {spark_master}")
```

3. In the next cell, read and engineer customer features:

```python
# Read customer_360 from Iceberg
customer_360 = spark.sql("""
    SELECT
      customer_id, age, country, is_premium,
      total_orders, lifetime_value, days_since_last_order,
      avg_order_value, event_timestamp
    FROM warehouse.analytics.customer_360
""")

# Demonstrate Spark feature engineering: log-transform skewed columns
customer_stats = (
    customer_360
    .withColumn("log_lifetime_value", log1p(col("lifetime_value").cast("double")))
    .withColumn("log_total_orders", log1p(col("total_orders").cast("double")))
    .withColumn("recency_bucket",
        when(col("days_since_last_order") <= 7, "recent")
        .when(col("days_since_last_order") <= 30, "active")
        .otherwise("lapsed"))
)

customer_stats.show(5)
print(f"customer_stats: {customer_stats.count()} rows")
```

4. Write feature Parquet files to MinIO:

```python
# Write Parquet for Feast
customer_stats.write.mode("overwrite").parquet("s3a://warehouse/feast/customer_stats/")
print("Written: s3a://warehouse/feast/customer_stats/")

# Customer behavior
customer_behavior = spark.sql("""
    SELECT customer_id, page_views_30d, add_to_cart_30d,
           support_tickets, checkout_rate, event_timestamp
    FROM warehouse.analytics.customer_behavior
""")
customer_behavior.write.mode("overwrite").parquet("s3a://warehouse/feast/customer_behavior/")
print("Written: s3a://warehouse/feast/customer_behavior/")

# Product stats
product_stats = spark.sql("""
    SELECT product_id, category, unit_price, times_ordered,
           units_sold, revenue, stock_qty, event_timestamp
    FROM warehouse.analytics.product_performance
""")
product_stats.write.mode("overwrite").parquet("s3a://warehouse/feast/product_stats/")
print("Written: s3a://warehouse/feast/product_stats/")

spark.stop()
print("Spark session stopped.")
```

### How to verify — Spark UI

1. Open `http://localhost:8080` (Spark Master UI).
2. Under **"Completed Applications"**, you should see `Lab1-FeatureEngineering`.

### How to verify — MinIO

1. Open `http://localhost:9001`.
2. Navigate to **warehouse** → **feast**.
3. You should see three folders: `customer_stats/`, `customer_behavior/`, `product_stats/`.
4. Each should contain Parquet files.

---

## Section 9 — Define and Apply Feast Features

### Goal

Create the Feast feature store configuration and feature definitions, then register them.

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

**Apply the feature definitions:**

```bash
docker compose exec feast sh -c "feast -c /opt/feast/project apply"
```

Expected output:

```
Applying changes for project retail_features
Created entity customer
Created entity product
Created feature view customer_stats
Created feature view customer_behavior
Created feature view product_stats
```

**Materialize features to the online store:**

```bash
docker compose exec feast sh -c \
  "feast -c /opt/feast/project materialize-incremental \$(date -u +%Y-%m-%dT%H:%M:%S)"
```

### How to verify — Feast UI

1. Open `http://localhost:6567`.
2. Click **"Feature Views"** — you should see `customer_stats`, `customer_behavior`, `product_stats`.
3. Click **"Entities"** — you should see `customer` and `product`.
4. Click **"Data Sources"** — you should see three sources pointing to `s3://warehouse/feast/...`.

---

## Section 10 — Train and Log Model to MLflow with PySpark MLlib

### Goal

Train a Random Forest classifier using PySpark MLlib on the churn dataset, log metrics and the Spark model to MLflow, and save the model for MLServer.

### What you will create

A notebook `train_model.ipynb` that trains the model with PySpark MLlib and interacts with MLflow.

### Steps

1. In JupyterHub, create `train_model.ipynb`.

2. In the first cell — create SparkSession (reuse the same config from Section 8):

```python
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
import mlflow
import mlflow.spark

PACKAGES = ",".join([
    "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.5.2",
    "org.apache.iceberg:iceberg-aws-bundle:1.5.2",
    "software.amazon.awssdk:url-connection-client:2.25.53",
    "org.apache.hadoop:hadoop-aws:3.3.4",
    "com.amazonaws:aws-java-sdk-bundle:1.12.262",
    "org.postgresql:postgresql:42.7.3",
])

aws_access_key = os.environ.get("AWS_ACCESS_KEY_ID", "mlplatform")
aws_secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "MinioSecure123")
spark_master   = os.environ.get("SPARK_MASTER", "spark://spark-master:7077")
s3_endpoint    = os.environ.get("AWS_S3_ENDPOINT", "http://minio:9000")
iceberg_uri    = os.environ.get("ICEBERG_JDBC_URI", "jdbc:postgresql://postgres-iceberg:5432/iceberg_catalog")

spark = (
    SparkSession.builder
    .appName("Lab1-ChurnModelTraining")
    .master(spark_master)
    .config("spark.jars.packages", PACKAGES)
    .config("spark.sql.extensions",
            "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
    .config("spark.sql.catalog.warehouse", "org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.warehouse.type", "jdbc")
    .config("spark.sql.catalog.warehouse.uri", iceberg_uri)
    .config("spark.sql.catalog.warehouse.jdbc.user",
            os.environ.get("ICEBERG_JDBC_USER", "iceberg"))
    .config("spark.sql.catalog.warehouse.jdbc.password",
            os.environ.get("ICEBERG_JDBC_PASSWORD", "iceberg123"))
    .config("spark.sql.catalog.warehouse.jdbc.schema-version", "V1")
    .config("spark.sql.catalog.warehouse.warehouse", "s3://warehouse/")
    .config("spark.sql.catalog.warehouse.io-impl",
            "org.apache.iceberg.aws.s3.S3FileIO")
    .config("spark.sql.catalog.warehouse.http-client.type", "urlconnection")
    .config("spark.sql.catalog.warehouse.client.region",
            os.environ.get("AWS_REGION", "us-east-1"))
    .config("spark.sql.catalog.warehouse.s3.endpoint", s3_endpoint)
    .config("spark.sql.catalog.warehouse.s3.path-style-access", "true")
    .config("spark.sql.catalog.warehouse.s3.access-key-id", aws_access_key)
    .config("spark.sql.catalog.warehouse.s3.secret-access-key", aws_secret_key)
    .config("spark.hadoop.fs.s3a.endpoint", s3_endpoint)
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .config("spark.hadoop.fs.s3a.aws.credentials.provider",
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
    .config("spark.hadoop.fs.s3a.access.key", aws_access_key)
    .config("spark.hadoop.fs.s3a.secret.key", aws_secret_key)
    .getOrCreate()
)
print(f"Spark {spark.version} ready")
```

3. In the second cell — load and inspect the training data:

```python
FEATURE_COLUMNS = [
    "age", "total_orders", "lifetime_value", "avg_order_value",
    "days_since_last_order", "page_views_30d", "support_tickets", "return_rate",
]

dataset = spark.sql("""
    SELECT * FROM warehouse.analytics.churn_training_dataset ORDER BY customer_id
""")

for fc in FEATURE_COLUMNS:
    dataset = dataset.withColumn(fc, col(fc).cast("double"))
dataset = dataset.withColumn("churn_label", col("churn_label").cast("double"))

print(f"Training dataset: {dataset.count()} rows")
dataset.groupBy("churn_label").count().show()
```

4. In the third cell — build and train the PySpark MLlib pipeline:

```python
from pyspark.ml import Pipeline
from pyspark.ml.classification import RandomForestClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator, MulticlassClassificationEvaluator
from pyspark.ml.feature import VectorAssembler

assembler = VectorAssembler(inputCols=FEATURE_COLUMNS, outputCol="features")
rf = RandomForestClassifier(
    featuresCol="features",
    labelCol="churn_label",
    numTrees=50,
    seed=42,
)
pipeline = Pipeline(stages=[assembler, rf])

train_df, test_df = dataset.randomSplit([0.7, 0.3], seed=42)
print(f"Train: {train_df.count()} | Test: {test_df.count()}")

model = pipeline.fit(train_df)
print("Pipeline fitted.")
```

5. In the fourth cell — evaluate:

```python
predictions = model.transform(test_df)

accuracy = float(
    MulticlassClassificationEvaluator(
        labelCol="churn_label", predictionCol="prediction", metricName="accuracy"
    ).evaluate(predictions)
)
auc = float(
    BinaryClassificationEvaluator(
        labelCol="churn_label", rawPredictionCol="rawPrediction", metricName="areaUnderROC"
    ).evaluate(predictions)
)
print(f"Accuracy: {accuracy:.4f}")
print(f"AUC:      {auc:.4f}")
```

6. In the fifth cell — log to MLflow:

```python
mlflow.set_tracking_uri(
    os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow:5000")
)
mlflow.set_experiment("retail-churn-demo")

with mlflow.start_run(run_name="lab1-pyspark-random-forest"):
    mlflow.log_params({
        "model_type": "PySpark_RandomForestClassifier",
        "num_trees": 50,
        "framework": "pyspark.ml",
        "test_size": 0.3,
    })
    mlflow.log_metrics({"accuracy": accuracy, "auc": auc})
    mlflow.spark.log_model(model, artifact_path="spark-model")
    mlflow.set_tags({
        "lab": "lab1",
        "dataset": "churn_training_dataset",
    })

print("Run logged to MLflow.")
```

7. In the sixth cell — save the MLflow model for MLServer:

```python
from pathlib import Path

model_dir = Path("/srv/jupyterhub/notebooks/churn-model")
mlflow_model_dir = model_dir / "mlflow_model"
mlflow_model_dir.mkdir(parents=True, exist_ok=True)

mlflow.spark.save_model(model, str(mlflow_model_dir))

import json
model_settings = {
    "name": "churn-model",
    "implementation": "mlserver_mlflow.MLflowRuntime",
    "parameters": {"uri": "./mlflow_model", "version": "v1"},
}
(model_dir / "model-settings.json").write_text(
    json.dumps(model_settings, indent=2), encoding="utf-8",
)
print(f"MLflow Spark model saved to {mlflow_model_dir}")
```

8. Save a scored dataset for Evidently:

```python
all_predictions = model.transform(dataset)
scored_pd = all_predictions.select(
    *FEATURE_COLUMNS, "churn_label", "prediction", "probability"
).toPandas()
scored_pd["prediction_probability"] = scored_pd["probability"].apply(lambda v: float(v[1]))
scored_pd = scored_pd.drop(columns=["probability"])
scored_pd.to_csv("/srv/jupyterhub/notebooks/scored_dataset.csv", index=False)
print(f"Scored dataset saved ({len(scored_pd)} rows)")

spark.stop()
print("Spark session stopped.")
```

### How to verify — MLflow UI

1. Open `http://localhost:5000` and log in.
2. Click **"retail-churn-demo"** experiment in the left sidebar.
3. You should see your new run `lab1-pyspark-random-forest`.
4. Click it. Verify:
   - **Parameters**: `model_type = PySpark_RandomForestClassifier`, `num_trees = 50`, `framework = pyspark.ml`
   - **Metrics**: `accuracy` and `auc` with values between 0 and 1
   - **Artifacts**: a `spark-model/` folder containing the logged Spark model

---

## Section 11 — Deploy Model to MLServer

### Goal

Copy the trained MLflow Spark model to the MLServer models directory and verify it serves predictions via REST API.

### Steps

1. Copy the model files from the notebook workspace to the MLServer volume:

```bash
# Copy the MLflow model directory
docker compose cp jupyterhub:/srv/jupyterhub/notebooks/churn-model/mlflow_model \
  ./mlserver/models/churn-model/mlflow_model

# Copy model-settings.json
docker compose cp jupyterhub:/srv/jupyterhub/notebooks/churn-model/model-settings.json \
  ./mlserver/models/churn-model/model-settings.json
```

2. Restart MLServer to pick up the new model:

```bash
docker compose restart mlserver
```

3. Wait about 15–20 seconds (the MLflow runtime takes slightly longer to initialize than sklearn), then verify:

```bash
curl -s http://localhost:8085/v2/models/churn-model | python3 -m json.tool
```

Expected output:

```json
{
    "name": "churn-model",
    "versions": ["v1"],
    "platform": "",
    "inputs": [],
    "outputs": []
}
```

4. Test a prediction. The MLflow Spark runtime accepts a `dataframe_split` input format:

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

5. You should get a JSON response with `"outputs"` containing a prediction (`0.0` = not churning, `1.0` = churning).

### What broken looks like

- If curl returns "Connection refused", MLServer is not running. Check `docker compose ps mlserver`.
- If the model endpoint returns 404, the `mlflow_model/` directory or `model-settings.json` is missing. List: `ls -la mlserver/models/churn-model/`.
- If it returns a 500 error, check MLServer logs: `docker compose logs mlserver --tail=50`. Missing Java or PySpark in the MLServer container is the most common cause.

---

## Section 12 — Generate Evidently Drift Report

### Goal

Create a data drift report comparing reference vs current scored data.

### Steps

1. In JupyterHub, create `generate_evidently.ipynb`.

2. Paste and run:

```python
from pathlib import Path
import pandas as pd
from evidently.metric_preset import DataDriftPreset, DataQualityPreset
from evidently.report import Report

scored = pd.read_csv("/srv/jupyterhub/notebooks/scored_dataset.csv")

split = max(4, len(scored) // 2)
reference = scored.iloc[:split].copy()
current = scored.iloc[split:].copy()

# Introduce artificial drift in avg_order_value (+15%)
current["avg_order_value"] = current["avg_order_value"] * 1.15
current["prediction_probability"] = current["prediction_probability"].clip(upper=1.0)

report = Report(metrics=[DataQualityPreset(), DataDriftPreset()])
report.run(reference_data=reference, current_data=current)

reports_dir = Path("/srv/jupyterhub/evidently/reports")
reports_dir.mkdir(parents=True, exist_ok=True)
report.save_html(str(reports_dir / "index.html"))
print("Evidently report saved")
```

3. Copy the report to the evidently-ui volume:

```bash
docker compose cp jupyterhub:/srv/jupyterhub/evidently/reports/index.html \
  ./evidently/reports/index.html
```

### How to verify

1. Open `http://localhost:8092`.
2. You should see the Evidently report with **Data Quality** and **Data Drift** sections.
3. In the **Data Drift** section, `avg_order_value` should show drift detected (because you inflated it by 15%).

---

## Section 13 — Create the Airflow DAG

### Goal

Wire all pipeline steps into an Airflow DAG so they run automatically on a daily schedule.

### What you will create

The file `airflow/dags/retail_pipeline.py`.

### Steps

1. Create the file `airflow/dags/retail_pipeline.py` with this content:

```python
"""
retail_pipeline.py — Daily orchestration for the ML platform.

Pipeline:
  verify_airbyte_sync → dbt_run_and_test → publish_features_and_train → refresh_docs_index

Airbyte runs externally via abctl. Trigger a sync from http://localhost:8000
before this DAG runs, or configure an Airbyte schedule.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "ml-platform",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

BOOTSTRAP = "python /opt/bootstrap/seed_demo.py"

VERIFY_RAW_TABLES_CMD = """
python3 -c "
import trino, sys
conn = trino.dbapi.connect(host='trino', port=8080, user='trino', catalog='iceberg', schema='retail_raw')
cur = conn.cursor()
cur.execute('SHOW TABLES FROM iceberg.retail_raw')
tables = {row[0] for row in cur.fetchall()}
expected = {'customers','products','orders','order_items','events','payments','shipments','support_tickets'}
missing = expected - tables
if missing:
    print(f'MISSING tables: {missing}', flush=True)
    print('Run an Airbyte sync from http://localhost:8000 first.', flush=True)
    sys.exit(1)
print(f'All 8 raw tables present: {sorted(tables)}', flush=True)
"
"""

with DAG(
    dag_id="retail_ml_pipeline",
    default_args=default_args,
    description="Airbyte ingest → dbt transform → Spark feature eng + PySpark MLlib train → serve",
    start_date=datetime(2024, 1, 1),
    schedule="0 2 * * *",
    catchup=False,
    tags=["ml", "retail", "teaching"],
) as dag:
    verify_sync = BashOperator(
        task_id="verify_airbyte_sync",
        bash_command=VERIFY_RAW_TABLES_CMD,
    )

    dbt_run = BashOperator(
        task_id="dbt_run_and_test",
        bash_command=(
            "dbt deps --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && "
            "dbt run --project-dir /opt/dbt/retail --profiles-dir /opt/dbt && "
            "dbt test --project-dir /opt/dbt/retail --profiles-dir /opt/dbt"
        ),
    )

    post_dbt = BashOperator(
        task_id="publish_features_and_train",
        bash_command=f"{BOOTSTRAP} --step post_dbt",
    )

    docs_refresh = BashOperator(
        task_id="refresh_docs_index",
        bash_command="test -f /opt/platform/bootstrap/seed_manifest.json",
    )

    verify_sync >> dbt_run >> post_dbt >> docs_refresh
```

2. Save the file. Airflow auto-detects new DAG files within about 30 seconds.

### How to verify — Airflow UI

1. Open `http://localhost:8082` and log in.
2. On the **DAGs** page, look for `retail_ml_pipeline`. It should appear within 1 minute.
3. If the DAG is paused (grey toggle on the left), click the toggle to unpause it.
4. Click the **Play** button (▶) → **"Trigger DAG"** to start a manual run.
5. Click the DAG name to open the **Grid** view.
6. Watch the 4 tasks run in sequence: `verify_airbyte_sync` → `dbt_run_and_test` → `publish_features_and_train` → `refresh_docs_index`.
7. Each task box should turn green when complete.

### What each task does

| Task | What it runs | What it produces |
|---|---|---|
| `verify_airbyte_sync` | Python Trino check | Confirms 8 raw tables exist (Airbyte must have synced) |
| `dbt_run_and_test` | `dbt deps && dbt run && dbt test` | Staging + mart tables in `analytics` schema |
| `publish_features_and_train` | `seed_demo.py --step post_dbt` | Feast parquet files (via PySpark), MLflow run, MLServer model |
| `refresh_docs_index` | checks for seed_manifest.json | Confirms artifacts were created |

### What failure looks like

- **`verify_airbyte_sync` is red**: Airbyte hasn't synced yet. Open `http://localhost:8000`, click your connection, and trigger a manual sync.
- **`dbt_run_and_test` is red**: dbt model errors. Read the dbt output in the task log.
- **`publish_features_and_train` is red**: Spark, MLflow, or MinIO connection errors. Check `docker compose logs platform-bootstrap`.

---

## Section 14 — Verify with Superset

### Goal

Create a simple chart in Superset that queries your dbt marts through Trino.

### Steps

1. Open `http://localhost:8088` and log in.

2. Go to **Settings** (gear icon) → **Database Connections** → **"+ Database"**.

3. Select **Trino**. Enter SQLAlchemy URI:
   ```
   trino://trino@trino:8080/iceberg/analytics
   ```

4. Click **"Test Connection"** — should show green success. Click **"Connect"**.

5. Go to **SQL Lab** → **SQL Editor** (top menu).

6. Select the Trino database you just added. Run this query:

```sql
SELECT country, COUNT(*) AS customers, AVG(lifetime_value) AS avg_ltv
FROM customer_360
GROUP BY country
ORDER BY avg_ltv DESC
```

7. You should see a results table with countries and their average lifetime values.

8. Click **"Create Chart"** above the results to turn it into a visualization.

---

## Section 15 — Monitor with Grafana and Prometheus

### Goal

Verify that Prometheus is scraping metrics and Grafana is displaying them.

### Steps

**Prometheus:**

1. Open `http://localhost:9090`.
2. Click **Status** → **Targets**.
3. You should see two targets, both showing **UP** (green):
   - `prometheus` (self-monitoring)
   - `demo_postgres` (PostgreSQL metrics via postgres-exporter)
4. Go back to the main page. In the query box, type `pg_up` and click **Execute**.
5. You should see `pg_up{instance="postgres-exporter-demo:9187"} = 1`.

**Grafana:**

1. Open `http://localhost:3000` and log in.
2. In the left sidebar, click **Dashboards**.
3. Click **"ML Platform Overview"** (provisioned automatically).
4. You should see panels showing PostgreSQL metrics (connections, uptime, etc.).

---

## Lab Complete

You have now built the entire pipeline from scratch:

1. ✅ Explored source data in CloudBeaver
2. ✅ Ingested 8 tables into Iceberg with Airbyte
3. ✅ Verified raw layer in Trino and MinIO
4. ✅ Built 8 dbt staging models + 4 mart models
5. ✅ Validated data with Great Expectations
6. ✅ Used PySpark for distributed feature engineering
7. ✅ Published Feast feature sources to MinIO and registered them
8. ✅ Trained a PySpark MLlib churn model and logged it to MLflow
9. ✅ Deployed the model to MLServer via mlserver-mlflow
10. ✅ Generated an Evidently drift report
11. ✅ Created an Airflow DAG for automated orchestration
12. ✅ Verified results in Superset, Grafana, and Prometheus

Every piece of this pipeline was written by you and is now running on the platform.
