select
  ticket_id,
  customer_id,
  priority,
  status,
  issue_type,
  cast(created_at as timestamp) as created_at,
  cast(resolved_at as timestamp) as resolved_at
from {{ source('retail_raw', 'support_tickets') }}
