select
  product_id,
  name,
  category,
  cast(unit_price as double) as unit_price,
  stock_qty
from {{ source('retail_raw', 'products') }}
