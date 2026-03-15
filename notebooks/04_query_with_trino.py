# Notebook 04: Use Trino as the query layer over Iceberg and PostgreSQL

import os

import pandas as pd
import trino

conn = trino.dbapi.connect(
    host=os.environ.get("TRINO_HOST", "trino"),
    port=int(os.environ.get("TRINO_PORT", "8080")),
    user=os.environ.get("TRINO_USER", "trino"),
    catalog=os.environ.get("TRINO_CATALOG", "iceberg"),
    schema=os.environ.get("TRINO_SCHEMA", "analytics"),
)
cursor = conn.cursor()

cursor.execute(
    """
    SELECT customer_id, country, lifetime_value, churn_label
    FROM iceberg.analytics.customer_360
    ORDER BY lifetime_value DESC
    LIMIT 20
    """
)
pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])

cursor.execute(
    """
    SELECT order_id, order_status, payment_status, shipment_status, total_amount
    FROM postgresql.public.order_ops_overview
    ORDER BY total_amount DESC
    LIMIT 10
    """
)
pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
