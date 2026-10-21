with category_revenue as (
    select p.category, sum(f.net_line_amount) as revenue
    from warehouse.fact_sales f
    join warehouse.dim_products p on p.product_key = f.product_key
    group by p.category
), totals as (
    select sum(revenue) as total_revenue from category_revenue
)
select
    category,
    round(revenue, 2) as revenue,
    round(100.0 * revenue / nullif(total_revenue, 0), 2) as contribution_percentage
from category_revenue
cross join totals
order by revenue desc, category;
