# notebooks/01_ingest_and_explore.py
# Run this in JupyterHub — paste cells one at a time
# or use: File > Open from Text > paste this file

# ── Cell 1: Create Spark session ─────────────────────────────
from pyspark.sql import SparkSession
import os

spark = SparkSession.builder \
    .appName("RetailIngest") \
    .config("spark.hadoop.fs.s3a.access.key",  os.environ.get("AWS_ACCESS_KEY_ID", "mlplatform")) \
    .config("spark.hadoop.fs.s3a.secret.key",  os.environ.get("AWS_SECRET_ACCESS_KEY", "Minio@Secure123")) \
    .getOrCreate()

spark.sql("CREATE NAMESPACE IF NOT EXISTS warehouse.retail")
print("Spark ready. Iceberg namespace created.")

# ── Cell 2: Ingest all tables from demo-postgres ─────────────
jdbc_url = "jdbc:postgresql://demo-postgres:5432/retail_db"
jdbc_props = {
    "user":     "analyst",
    "password": "analyst123",
    "driver":   "org.postgresql.Driver"
}

tables = ["customers", "orders", "order_items", "events", "products"]
for table in tables:
    df = spark.read.jdbc(jdbc_url, f"public.{table}", properties=jdbc_props)
    df.writeTo(f"warehouse.retail.{table}").createOrReplace()
    print(f"  {table}: {df.count()} rows → warehouse.retail.{table}")

print("Ingest complete. Check MinIO at http://localhost:9001 → warehouse bucket.")

# ── Cell 3: Verify data in Iceberg ───────────────────────────
spark.sql("SHOW TABLES IN warehouse.retail").show()
spark.sql("SELECT * FROM warehouse.retail.customers LIMIT 5").show()

# ── Cell 4: Create feature table for Feast ───────────────────
from pyspark.sql import functions as F

customer_features = spark.sql("""
    SELECT
        c.customer_id,
        c.age,
        c.country,
        c.is_premium,
        COALESCE(o.total_orders, 0)         AS total_orders,
        COALESCE(o.lifetime_value, 0.0)     AS lifetime_value,
        COALESCE(o.days_since_last_order, 999) AS days_since_last_order,
        COALESCE(o.avg_order_value, 0.0)    AS avg_order_value,
        current_timestamp()                 AS event_timestamp
    FROM warehouse.retail.customers c
    LEFT JOIN (
        SELECT
            customer_id,
            COUNT(*)                               AS total_orders,
            SUM(total_amount)                      AS lifetime_value,
            AVG(total_amount)                      AS avg_order_value,
            DATEDIFF(current_date(), MAX(order_date)) AS days_since_last_order
        FROM warehouse.retail.orders
        WHERE status = 'completed'
        GROUP BY customer_id
    ) o ON c.customer_id = o.customer_id
""")

# Write as Parquet to MinIO so Feast can read it
customer_features.write \
    .mode("overwrite") \
    .parquet("s3a://warehouse/retail/customer_features/")

print(f"Feature table written: {customer_features.count()} rows")
customer_features.show()

# ── Cell 5: Create behavioral feature table ──────────────────
behavior_features = spark.sql("""
    SELECT
        customer_id,
        COUNT(*) FILTER (WHERE event_type = 'page_view')     AS page_views_30d,
        COUNT(*) FILTER (WHERE event_type = 'add_to_cart')   AS add_to_cart_30d,
        COUNT(*) FILTER (WHERE event_type = 'support_ticket') AS support_tickets,
        CASE
            WHEN COUNT(*) FILTER (WHERE event_type='add_to_cart') = 0 THEN 0.0
            ELSE COUNT(*) FILTER (WHERE event_type='checkout') * 1.0
               / COUNT(*) FILTER (WHERE event_type='add_to_cart')
        END AS checkout_rate,
        current_timestamp() AS event_timestamp
    FROM warehouse.retail.events
    GROUP BY customer_id
""")

behavior_features.write \
    .mode("overwrite") \
    .parquet("s3a://warehouse/retail/customer_behavior/")

print(f"Behavior features written: {behavior_features.count()} rows")

# ── Cell 6: Retrieve features from Feast ─────────────────────
# (Run this AFTER feast apply has completed — check container logs)
import pandas as pd
from feast import FeatureStore

store = FeatureStore(repo_path="/opt/feast/project")

entity_df = pd.DataFrame({
    "customer_id":      [1, 2, 3, 4, 5],
    "event_timestamp":  pd.Timestamp.now(tz="UTC")
})

features = store.get_historical_features(
    entity_df=entity_df,
    features=[
        "customer_stats:total_orders",
        "customer_stats:lifetime_value",
        "customer_stats:days_since_last_order",
        "customer_stats:is_premium",
        "customer_behavior:support_tickets",
    ]
).to_df()

print(features)
