with orders as (
    select distinct order_id, order_status
    from warehouse.fact_sales
)
select
    count(*) as total_orders,
    count(*) filter (where order_status = 'cancelled') as cancelled_orders,
    round(
        100.0 * count(*) filter (where order_status = 'cancelled') / nullif(count(*), 0),
        2
    ) as cancelled_order_percentage
from orders;
