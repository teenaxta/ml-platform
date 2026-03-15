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