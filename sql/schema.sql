begin;

create schema if not exists warehouse;
create schema if not exists ops;

create table if not exists warehouse.dim_customers (
    customer_key bigint generated always as identity primary key,
    customer_id text not null,
    first_name text not null,
    last_name text not null,
    email text,
    city text,
    state text,
    country_code text not null,
    registered_at timestamptz,
    customer_status text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint dim_customers_customer_id_uk unique (customer_id),
    constraint dim_customers_country_code_ck check (char_length(country_code) = 2),
    constraint dim_customers_status_ck check (customer_status in ('active', 'inactive'))
);

create table if not exists warehouse.dim_products (
    product_key bigint generated always as identity primary key,
    product_id text not null,
    product_name text not null,
    category text not null,
    current_unit_price numeric(12, 2) not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint dim_products_product_id_uk unique (product_id),
    constraint dim_products_price_ck check (current_unit_price >= 0)
);

create table if not exists warehouse.dim_dates (
    date_key integer primary key,
    full_date date not null,
    day_of_month smallint not null,
    month_number smallint not null,
    month_name text not null,
    quarter_number smallint not null,
    year_number smallint not null,
    day_of_week smallint not null,
    day_name text not null,
    is_weekend boolean not null,
    constraint dim_dates_full_date_uk unique (full_date),
    constraint dim_dates_day_ck check (day_of_month between 1 and 31),
    constraint dim_dates_month_ck check (month_number between 1 and 12),
    constraint dim_dates_quarter_ck check (quarter_number between 1 and 4),
    constraint dim_dates_day_of_week_ck check (day_of_week between 1 and 7)
);

create table if not exists warehouse.fact_sales (
    sales_key bigint generated always as identity primary key,
    order_item_id text not null,
    order_id text not null,
    customer_key bigint not null,
    product_key bigint not null,
    order_date_key integer not null,
    order_timestamp timestamptz not null,
    order_status text not null,
    payment_method text,
    quantity integer not null,
    unit_price numeric(12, 2) not null,
    gross_line_amount numeric(14, 2) not null,
    net_line_amount numeric(14, 2) not null,
    source_file text not null,
    source_updated_at timestamptz,
    loaded_at timestamptz not null default now(),
    constraint fact_sales_order_item_id_uk unique (order_item_id),
    constraint fact_sales_customer_fk foreign key (customer_key)
        references warehouse.dim_customers (customer_key),
    constraint fact_sales_product_fk foreign key (product_key)
        references warehouse.dim_products (product_key),
    constraint fact_sales_date_fk foreign key (order_date_key)
        references warehouse.dim_dates (date_key),
    constraint fact_sales_status_ck check (
        order_status in ('completed', 'cancelled', 'returned', 'pending')
    ),
    constraint fact_sales_quantity_ck check (quantity > 0),
    constraint fact_sales_unit_price_ck check (unit_price >= 0),
    constraint fact_sales_gross_amount_ck check (gross_line_amount >= 0)
);

create index if not exists fact_sales_customer_key_idx
    on warehouse.fact_sales (customer_key);
create index if not exists fact_sales_product_key_idx
    on warehouse.fact_sales (product_key);
create index if not exists fact_sales_order_date_key_idx
    on warehouse.fact_sales (order_date_key);
create index if not exists fact_sales_order_id_idx
    on warehouse.fact_sales (order_id);
create index if not exists fact_sales_status_date_idx
    on warehouse.fact_sales (order_status, order_date_key);

create table if not exists ops.pipeline_runs (
    run_id bigint generated always as identity primary key,
    batch_id text not null,
    pipeline_version text not null,
    source_name text not null,
    status text not null,
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    rows_read bigint not null default 0,
    rows_loaded bigint not null default 0,
    rows_rejected bigint not null default 0,
    error_message text,
    constraint pipeline_runs_batch_id_uk unique (batch_id),
    constraint pipeline_runs_status_ck check (
        status in ('running', 'succeeded', 'failed', 'partially_succeeded')
    ),
    constraint pipeline_runs_counts_ck check (
        rows_read >= 0 and rows_loaded >= 0 and rows_rejected >= 0
    ),
    constraint pipeline_runs_timestamps_ck check (
        completed_at is null or completed_at >= started_at
    )
);

create index if not exists pipeline_runs_status_started_idx
    on ops.pipeline_runs (status, started_at desc);

create table if not exists ops.processed_source_files (
    file_id bigint generated always as identity primary key,
    run_id bigint not null,
    source_uri text not null,
    content_checksum text not null,
    file_size_bytes bigint not null,
    source_last_modified_at timestamptz,
    processed_at timestamptz not null default now(),
    rows_read bigint not null default 0,
    rows_rejected bigint not null default 0,
    constraint processed_source_files_run_fk foreign key (run_id)
        references ops.pipeline_runs (run_id),
    constraint processed_source_files_uri_checksum_uk
        unique (source_uri, content_checksum),
    constraint processed_source_files_size_ck check (file_size_bytes >= 0),
    constraint processed_source_files_counts_ck check (
        rows_read >= 0 and rows_rejected >= 0 and rows_rejected <= rows_read
    )
);

create index if not exists processed_source_files_run_id_idx
    on ops.processed_source_files (run_id);

create table if not exists ops.rejected_records (
    rejection_id bigint generated always as identity primary key,
    run_id bigint not null,
    source_uri text not null,
    source_row_number bigint,
    record_identifier text,
    rejection_stage text not null,
    rejection_reason text not null,
    raw_payload jsonb not null,
    rejected_at timestamptz not null default now(),
    constraint rejected_records_run_fk foreign key (run_id)
        references ops.pipeline_runs (run_id),
    constraint rejected_records_stage_ck check (
        rejection_stage in ('extract', 'validate', 'transform', 'load')
    ),
    constraint rejected_records_row_ck check (
        source_row_number is null or source_row_number > 0
    )
);

create index if not exists rejected_records_run_id_idx
    on ops.rejected_records (run_id);
create index if not exists rejected_records_source_uri_idx
    on ops.rejected_records (source_uri);

create table if not exists ops.data_quality_results (
    quality_result_id bigint generated always as identity primary key,
    run_id bigint not null,
    check_name text not null,
    dataset_name text not null,
    status text not null,
    records_checked bigint not null default 0,
    records_failed bigint not null default 0,
    observed_value numeric,
    expected_value text,
    details jsonb not null default '{}'::jsonb,
    checked_at timestamptz not null default now(),
    constraint data_quality_results_run_fk foreign key (run_id)
        references ops.pipeline_runs (run_id),
    constraint data_quality_results_status_ck check (
        status in ('passed', 'failed', 'warning')
    ),
    constraint data_quality_results_counts_ck check (
        records_checked >= 0
        and records_failed >= 0
        and records_failed <= records_checked
    )
);

create index if not exists data_quality_results_run_id_idx
    on ops.data_quality_results (run_id);
create index if not exists data_quality_results_status_idx
    on ops.data_quality_results (status);

commit;
