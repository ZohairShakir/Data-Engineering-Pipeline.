select
    d.full_date as order_date,
    count(distinct f.order_id) as order_count,
    round(sum(f.net_line_amount), 2) as revenue
from warehouse.fact_sales f
join warehouse.dim_dates d on d.date_key = f.order_date_key
group by d.full_date
order by d.full_date;
