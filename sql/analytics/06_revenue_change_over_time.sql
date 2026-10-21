with monthly_revenue as (
    select
        date_trunc('month', d.full_date)::date as month_start,
        sum(f.net_line_amount) as revenue
    from warehouse.fact_sales f
    join warehouse.dim_dates d on d.date_key = f.order_date_key
    group by date_trunc('month', d.full_date)::date
), changes as (
    select
        month_start,
        revenue,
        lag(revenue) over (order by month_start) as previous_revenue
    from monthly_revenue
)
select
    to_char(month_start, 'YYYY-MM') as month,
    round(revenue, 2) as revenue,
    round(
        100.0 * (revenue - previous_revenue) / nullif(abs(previous_revenue), 0),
        2
    ) as month_over_month_pct
from changes
order by month_start;
