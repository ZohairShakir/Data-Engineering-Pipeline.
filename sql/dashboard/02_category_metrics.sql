with order_category as (
    select
        p.category,
        f.order_id,
        max(f.order_status) as order_status,
        sum(f.net_line_amount) as order_value
    from warehouse.fact_sales f
    join warehouse.dim_products p on p.product_key = f.product_key
    group by p.category, f.order_id
)
select
    category,
    round(sum(order_value), 2) as net_revenue,
    count(*) as order_count,
    round(
        avg(order_value) filter (where order_status in ('completed', 'returned')),
        2
    ) as average_order_value,
    round(
        100.0 * count(*) filter (where order_status = 'cancelled') / nullif(count(*), 0),
        2
    ) as cancelled_order_percentage
from order_category
group by category
order by category;
