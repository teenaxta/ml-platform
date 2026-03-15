
  
    

    create table "iceberg"."analytics"."customer_360__dbt_tmp"
      
      
    as (
      with customers as (
    select * from "iceberg"."analytics"."stg_customers"
),
orders as (
    select * from "iceberg"."analytics"."stg_orders"
),
payments as (
    select * from "iceberg"."analytics"."stg_payments"
),
support as (
    select * from "iceberg"."analytics"."stg_support_tickets"
),
behavior as (
    select * from "iceberg"."analytics"."customer_behavior"
),
orders_agg as (
    select
        customer_id,
        count(*) as total_orders,
        sum(case when status = 'completed' then total_amount else 0 end) as lifetime_value,
        avg(case when status = 'completed' then total_amount end) as avg_order_value,
        date_diff('day', cast(max(order_date) as date), current_date) as days_since_last_order,
        sum(case when status = 'returned' then 1 else 0 end) * 1.0 / nullif(count(*), 0) as return_rate
    from orders
    group by 1
),
payments_agg as (
    select
        o.customer_id,
        count(*) filter (where p.payment_status = 'captured') as successful_payments
    from payments p
    join orders o on p.order_id = o.order_id
    group by 1
),
support_agg as (
    select
        customer_id,
        count(*) as opened_tickets
    from support
    group by 1
)

select
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email,
    c.country,
    c.age,
    c.signup_date,
    c.is_premium,
    coalesce(o.total_orders, 0) as total_orders,
    coalesce(o.lifetime_value, 0.0) as lifetime_value,
    coalesce(o.avg_order_value, 0.0) as avg_order_value,
    coalesce(o.days_since_last_order, 999) as days_since_last_order,
    coalesce(o.return_rate, 0.0) as return_rate,
    coalesce(p.successful_payments, 0) as successful_payments,
    coalesce(s.opened_tickets, 0) as support_tickets,
    coalesce(b.page_views_30d, 0) as page_views_30d,
    coalesce(b.add_to_cart_30d, 0) as add_to_cart_30d,
    coalesce(b.checkout_events_30d, 0) as checkout_events_30d,
    coalesce(b.checkout_rate, 0.0) as checkout_rate,
    case
        when coalesce(o.days_since_last_order, 999) > 35
          or coalesce(s.opened_tickets, 0) >= 2
          or coalesce(o.return_rate, 0.0) >= 0.30
        then 1
        else 0
    end as churn_label,
    current_timestamp as event_timestamp
from customers c
left join orders_agg o on c.customer_id = o.customer_id
left join payments_agg p on c.customer_id = p.customer_id
left join support_agg s on c.customer_id = s.customer_id
left join behavior b on c.customer_id = b.customer_id
    );

  