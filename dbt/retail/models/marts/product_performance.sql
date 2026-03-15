with products as (
    select * from {{ ref('stg_products') }}
),
items as (
    select * from {{ ref('stg_order_items') }}
)

select
    p.product_id,
    p.name,
    p.category,
    p.unit_price,
    p.stock_qty,
    count(i.item_id) as times_ordered,
    coalesce(sum(i.quantity), 0) as units_sold,
    coalesce(sum(i.quantity * i.unit_price), 0.0) as revenue,
    current_timestamp as event_timestamp
from products p
left join items i on p.product_id = i.product_id
group by 1, 2, 3, 4, 5
