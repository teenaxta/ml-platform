
  
    

    create table "iceberg"."analytics"."stg_customers__dbt_tmp"
      
      
    as (
      select
  customer_id,
  first_name,
  last_name,
  email,
  country,
  age,
  signup_date,
  is_premium
from "iceberg"."retail_raw"."customers"
    );

  