select
    c.customer_id,
    concat(c.first_name, ' ', c.last_name) as customer_name,
    count(distinct f.order_id) as order_count,
    round(sum(f.net_line_amount), 2) as lifetime_value
from warehouse.fact_sales f
join warehouse.dim_customers c on c.customer_key = f.customer_key
group by c.customer_id, c.first_name, c.last_name
order by lifetime_value desc, c.customer_id
limit 10;
