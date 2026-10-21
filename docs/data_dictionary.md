# Data dictionary

## Source datasets

| Dataset | Natural key | Required analytical fields | Partitioning |
|---|---|---|---|
| `customers` | `customer_id` | name, email, city/state/country, registered timestamp, status | one CSV |
| `products` | `product_id` | name, category, current unit price, active flag | one CSV |
| `orders` | `order_id` | customer, order timestamp, status, stated total | monthly CSVs |
| `order_items` | `order_item_id` | order, product, quantity, unit price, line amount | monthly CSVs |
| `payments` | `payment_id` | order, method, status, amount, paid timestamp | monthly CSVs |

The reference generator produces 38 files: two master files and 12 monthly
files for each of orders, order items, and payments. All content is synthetic.
See [dataset.md](dataset.md) for provenance and limitations.

## Transformation rules

| Rule | Behavior |
|---|---|
| Stable identifiers | trim whitespace; blank and duplicate keys are rejected |
| Categories/statuses | trim and lowercase before validation |
| Dates | parse as UTC timestamps; invalid dates are rejected |
| Money | parse numeric values; negative unit prices/totals are rejected |
| Relationships | customer/order, product/item, and payment/order references must exist |
| Totals | item sum must match stated order total; payment amount/status must agree |
| Completed revenue | `quantity × unit_price` |
| Returned revenue | negative `quantity × unit_price` |
| Cancelled/pending revenue | zero |

Rejected rows retain dataset, source URI, source row number, record identifier,
pipeline stage, reason, and raw payload.

## Warehouse tables

### `warehouse.dim_customers`

Grain: one current customer.

| Column | Type | Meaning |
|---|---|---|
| `customer_key` | `bigint identity` | warehouse surrogate primary key |
| `customer_id` | `text unique` | source natural key used for upserts |
| `first_name`, `last_name` | `text` | normalized display name parts |
| `email` | `text` | synthetic email; nullable |
| `city`, `state` | `text` | synthetic location attributes |
| `country_code` | `text` | two-character country code |
| `registered_at` | `timestamptz` | source registration time |
| `customer_status` | `text` | `active` or `inactive` |

### `warehouse.dim_products`

Grain: one current product.

| Column | Type | Meaning |
|---|---|---|
| `product_key` | `bigint identity` | warehouse surrogate primary key |
| `product_id` | `text unique` | source natural key used for upserts |
| `product_name` | `text` | product display name |
| `category` | `text` | normalized analytical category |
| `current_unit_price` | `numeric(12,2)` | current source-list price |
| `is_active` | `boolean` | current availability flag |

### `warehouse.dim_dates`

Grain: one calendar date.

| Column | Type | Meaning |
|---|---|---|
| `date_key` | `integer` | `YYYYMMDD` primary key |
| `full_date` | `date unique` | calendar date |
| `day_of_month` | `smallint` | 1–31 |
| `month_number`, `month_name` | number/text | calendar month |
| `quarter_number` | `smallint` | 1–4 |
| `year_number` | `smallint` | calendar year |
| `day_of_week`, `day_name` | number/text | ISO weekday and label |
| `is_weekend` | `boolean` | Saturday/Sunday flag |

### `warehouse.fact_sales`

Grain: one order item. The unique `order_item_id` is the idempotent upsert key.

| Column | Type | Meaning |
|---|---|---|
| `sales_key` | `bigint identity` | surrogate primary key |
| `order_item_id` | `text unique` | source fact natural key |
| `order_id` | `text` | degenerate dimension for order aggregation |
| `customer_key` | `bigint FK` | customer dimension reference |
| `product_key` | `bigint FK` | product dimension reference |
| `order_date_key` | `integer FK` | date dimension reference |
| `order_timestamp` | `timestamptz` | source order time |
| `order_status` | `text` | completed/cancelled/returned/pending |
| `payment_method` | `text` | normalized payment method |
| `quantity` | `integer` | units; must be positive |
| `unit_price` | `numeric(12,2)` | captured transaction unit price |
| `gross_line_amount` | `numeric(14,2)` | quantity × unit price |
| `net_line_amount` | `numeric(14,2)` | status-adjusted analytical revenue |
| `source_file` | `text` | lineage URI for the item row |
| `source_updated_at` | `timestamptz` | source modification timestamp |
| `loaded_at` | `timestamptz` | last warehouse upsert time |

## Operational tables

| Table | Grain | Key fields | Purpose |
|---|---|---|---|
| `ops.pipeline_runs` | one attempt | batch ID, version, status, counts, error | execution history and recovery |
| `ops.processed_source_files` | one source URI per successful/partial run | run, dataset, URI, SHA-256, size, row counts | lineage and checksum skip decisions |
| `ops.rejected_records` | one invalid source row | source row identity, stage, reason, JSON payload | quarantine audit |
| `ops.data_quality_results` | one check per run/dataset | status, checked/failed counts, expected/observed, JSON details | measurable data-quality evidence |

`processed_source_files` is intentionally tied to a run. The composite lookup
index on URI/checksum answers whether matching content has already been loaded;
the run join ensures the decision is scoped to the pipeline version.
