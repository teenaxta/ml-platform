select
  customer_id,
  first_name,
  last_name,
  email,
  country,
  age,
  signup_date,
  is_premium
from {{ source('retail_raw', 'customers') }}
