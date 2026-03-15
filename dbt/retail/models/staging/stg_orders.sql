select
  order_id,
  customer_id,
  cast(order_date as timestamp) as order_date,
  status,
  cast(total_amount as double) as total_amount
from {{ source('retail_raw', 'orders') }}
