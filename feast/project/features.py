"""
features.py  —  Feast feature definitions for the retail ML platform

These features are sourced from Parquet files written by Spark/dbt into MinIO.
Run `feast apply` (done automatically by the container) to register them.

Usage in notebooks:
    from feast import FeatureStore
    store = FeatureStore(repo_path="/opt/feast/project")

    entity_df = pd.DataFrame({
        "customer_id": [1, 2, 3],
        "event_timestamp": pd.Timestamp.now(tz="UTC")
    })

    features = store.get_historical_features(
        entity_df=entity_df,
        features=[
            "customer_stats:total_orders",
            "customer_stats:lifetime_value",
            "customer_stats:days_since_last_order",
            "customer_stats:is_premium",
            "customer_behavior:support_tickets",
            "customer_behavior:page_views_30d",
        ]
    ).to_df()
"""

import os
from datetime import timedelta
from feast import Entity, FeatureView, Field, FileSource, ValueType
from feast.data_format import ParquetFormat
from feast.types import Float64, Int64, Bool, String


S3_ENDPOINT = os.getenv("AWS_S3_ENDPOINT_URL", "http://minio:9000")


# ── Entities ─────────────────────────────────────────────────
# An Entity is the primary key — everything is looked up by customer_id

customer = Entity(
    name="customer",
    join_keys=["customer_id"],
    value_type=ValueType.INT64,
    description="A retail customer identified by their integer ID",
)

product = Entity(
    name="product",
    join_keys=["product_id"],
    value_type=ValueType.INT64,
    description="A product in the retail catalogue",
)


# ── Sources ───────────────────────────────────────────────────
# These point to Parquet files in MinIO written by Spark/dbt.
# The paths match what the example notebook writes.
# Update s3:// paths if your Spark writes to different locations.

customer_stats_source = FileSource(
    name="customer_stats_source",
    path="s3://warehouse/feast/customer_stats/",
    file_format=ParquetFormat(),
    timestamp_field="event_timestamp",
    s3_endpoint_override=S3_ENDPOINT,
    description="Aggregated customer purchase statistics from dbt model",
)

customer_behavior_source = FileSource(
    name="customer_behavior_source",
    path="s3://warehouse/feast/customer_behavior/",
    file_format=ParquetFormat(),
    timestamp_field="event_timestamp",
    s3_endpoint_override=S3_ENDPOINT,
    description="Customer behavioural signals from the events table",
)

product_stats_source = FileSource(
    name="product_stats_source",
    path="s3://warehouse/feast/product_stats/",
    file_format=ParquetFormat(),
    timestamp_field="event_timestamp",
    s3_endpoint_override=S3_ENDPOINT,
    description="Product-level aggregated statistics",
)


# ── Feature Views ─────────────────────────────────────────────
# A FeatureView groups related features together under one entity.

customer_stats = FeatureView(
    name="customer_stats",
    entities=[customer],
    ttl=timedelta(days=30),
    schema=[
        Field(name="age",                  dtype=Int64,   description="Customer age in years"),
        Field(name="country",              dtype=String,  description="Customer country"),
        Field(name="is_premium",           dtype=Bool,    description="Premium subscription flag"),
        Field(name="total_orders",         dtype=Int64,   description="Total number of completed orders"),
        Field(name="lifetime_value",       dtype=Float64, description="Sum of completed order amounts (USD)"),
        Field(name="days_since_last_order",dtype=Int64,   description="Days since most recent completed order"),
        Field(name="avg_order_value",      dtype=Float64, description="Average order value across all completed orders"),
    ],
    source=customer_stats_source,
    description="Core customer purchase statistics — updated daily by dbt",
    tags={"team": "ml-platform", "domain": "customer"},
)

customer_behavior = FeatureView(
    name="customer_behavior",
    entities=[customer],
    ttl=timedelta(days=14),
    schema=[
        Field(name="page_views_30d",      dtype=Int64,   description="Page view events in last 30 days"),
        Field(name="add_to_cart_30d",     dtype=Int64,   description="Add-to-cart events in last 30 days"),
        Field(name="support_tickets",     dtype=Int64,   description="Total lifetime support tickets"),
        Field(name="checkout_rate",       dtype=Float64, description="Ratio of checkouts to add-to-cart events"),
    ],
    source=customer_behavior_source,
    description="Customer behavioural engagement signals — updated daily",
    tags={"team": "ml-platform", "domain": "engagement"},
)

product_stats = FeatureView(
    name="product_stats",
    entities=[product],
    ttl=timedelta(days=7),
    schema=[
        Field(name="category",       dtype=String,  description="Product category"),
        Field(name="unit_price",     dtype=Float64, description="Current unit price"),
        Field(name="times_ordered",  dtype=Int64,   description="Number of times this product was ordered"),
        Field(name="units_sold",     dtype=Int64,   description="Total units sold"),
        Field(name="revenue",        dtype=Float64, description="Total revenue generated"),
        Field(name="stock_qty",      dtype=Int64,   description="Current stock quantity"),
    ],
    source=product_stats_source,
    description="Product performance statistics — updated daily",
    tags={"team": "ml-platform", "domain": "product"},
)
