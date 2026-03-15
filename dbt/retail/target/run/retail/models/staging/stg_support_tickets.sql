
  
    

    create table "iceberg"."analytics"."stg_support_tickets__dbt_tmp"
      
      
    as (
      select
  ticket_id,
  customer_id,
  priority,
  status,
  issue_type,
  cast(created_at as timestamp) as created_at,
  cast(resolved_at as timestamp) as resolved_at
from "iceberg"."retail_raw"."support_tickets"
    );

  