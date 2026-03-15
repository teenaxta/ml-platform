select
  item_id,
  order_id,
  product_id,
  quantity,
  cast(unit_price as double) as unit_price
from "iceberg"."retail_raw"."order_items"