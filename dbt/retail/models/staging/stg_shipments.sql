select
  shipment_id,
  order_id,
  carrier,
  shipment_status,
  cast(shipped_at as timestamp) as shipped_at,
  cast(delivered_at as timestamp) as delivered_at
from {{ source('retail_raw', 'shipments') }}
