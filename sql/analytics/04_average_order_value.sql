with order_values as (
    select order_id, sum(net_line_amount) as order_value
    from warehouse.fact_sales
    where order_status in ('completed', 'returned')
    group by order_id
)
select
    round(avg(order_value), 2) as average_order_value,
    count(*) as included_orders
from order_values;
