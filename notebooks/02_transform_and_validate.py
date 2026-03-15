# Notebook 02: Query dbt outputs and inspect Great Expectations inputs

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

cursor.execute("SELECT * FROM iceberg.analytics.customer_360 ORDER BY lifetime_value DESC LIMIT 10")
customer_360 = pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
customer_360

cursor.execute("SELECT * FROM iceberg.analytics.product_performance ORDER BY revenue DESC LIMIT 10")
product_performance = pd.DataFrame(cursor.fetchall(), columns=[c[0] for c in cursor.description])
product_performance

customer_360.to_csv("/srv/jupyterhub/great_expectations/data/customer_360_from_notebook.csv", index=False)
print("Saved a local CSV snapshot you can validate with Great Expectations.")
