with events as (
    select * from "iceberg"."analytics"."stg_events"
)

select
    customer_id,
    count_if(event_type = 'page_view') as page_views_30d,
    count_if(event_type = 'add_to_cart') as add_to_cart_30d,
    count_if(event_type = 'checkout') as checkout_events_30d,
    count_if(event_type = 'support_ticket') as support_tickets,
    case
        when count_if(event_type = 'add_to_cart') = 0 then 0.0
        else cast(count_if(event_type = 'checkout') as double) / cast(count_if(event_type = 'add_to_cart') as double)
    end as checkout_rate,
    current_timestamp as event_timestamp
from events
group by 1