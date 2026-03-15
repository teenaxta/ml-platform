
  
    

    create table "iceberg"."analytics"."stg_events__dbt_tmp"
      
      
    as (
      select
  event_id,
  customer_id,
  event_type,
  cast(event_ts as timestamp) as event_ts
from "iceberg"."retail_raw"."events"
    );

  