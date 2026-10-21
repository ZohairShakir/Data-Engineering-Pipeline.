select
    p.category,
    to_char(d.full_date, 'YYYY-MM') as month,
    round(sum(f.net_line_amount), 2) as revenue,
    count(distinct f.order_id) as order_count
from warehouse.fact_sales f
join warehouse.dim_products p on p.product_key = f.product_key
join warehouse.dim_dates d on d.date_key = f.order_date_key
group by p.category, d.year_number, d.month_number, to_char(d.full_date, 'YYYY-MM')
order by p.category, d.year_number, d.month_number;
