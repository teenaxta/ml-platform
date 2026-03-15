select
  payment_id,
  order_id,
  payment_method,
  payment_status,
  cast(amount as double) as amount,
  cast(paid_at as timestamp) as paid_at
from {{ source('retail_raw', 'payments') }}
