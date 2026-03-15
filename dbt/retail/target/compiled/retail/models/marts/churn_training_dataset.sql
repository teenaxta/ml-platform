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
from "iceberg"."analytics"."customer_360"