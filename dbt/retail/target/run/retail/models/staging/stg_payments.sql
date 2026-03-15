
  
    

    create table "iceberg"."analytics"."stg_payments__dbt_tmp"
      
      
    as (
      select
  payment_id,
  order_id,
  payment_method,
  payment_status,
  cast(amount as double) as amount,
  cast(paid_at as timestamp) as paid_at
from "iceberg"."retail_raw"."payments"
    );

  