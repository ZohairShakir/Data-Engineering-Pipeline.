select
    p.product_id,
    p.product_name,
    p.category,
    round(sum(f.net_line_amount), 2) as revenue,
    sum(f.quantity) as units
from warehouse.fact_sales f
join warehouse.dim_products p on p.product_key = f.product_key
group by p.product_id, p.product_name, p.category
order by revenue desc, p.product_id;
