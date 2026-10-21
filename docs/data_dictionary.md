# Data dictionary

## Source datasets

| Dataset | Natural key | Important fields | Notes |
|---|---|---|---|
| customers | `customer_id` | name, email, location, status | Synthetic identity data |
| products | `product_id` | name, category, unit price | Six normalized categories |
| orders | `order_id` | customer, timestamp, status, total | Monthly partitioned CSVs |
| order_items | `order_item_id` | order, product, quantity, amounts | One to four rows per order |
| payments | `payment_id` | order, method, status, amount | Exactly one per order |

## Warehouse tables

| Table | Grain | Primary key | Natural/unique key |
|---|---|---|---|
| `warehouse.dim_customers` | one current customer | `customer_key` | `customer_id` |
| `warehouse.dim_products` | one current product | `product_key` | `product_id` |
| `warehouse.dim_dates` | one calendar date | `date_key` (`YYYYMMDD`) | `full_date` |
| `warehouse.fact_sales` | one order item | `sales_key` | `order_item_id` |
| `ops.pipeline_runs` | one pipeline attempt | `run_id` | `batch_id` |
| `ops.processed_source_files` | one content version of a source file | `file_id` | source URI + checksum |
| `ops.rejected_records` | one rejected source row | `rejection_id` | none |
| `ops.data_quality_results` | one check result per run/dataset | `quality_result_id` | none |

`gross_line_amount` represents quantity multiplied by unit price.
`net_line_amount` will apply order-status business rules during transformation;
those rules will be implemented and tested in Phase 2.
