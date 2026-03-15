
  
    

    create table "iceberg"."analytics"."stg_products__dbt_tmp"
      
      
    as (
      select
  product_id,
  name,
  category,
  cast(unit_price as double) as unit_price,
  stock_qty
from "iceberg"."retail_raw"."products"
    );

  