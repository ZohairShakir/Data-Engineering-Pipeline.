# Architecture

## Phase 1 local architecture

```mermaid
flowchart LR
    G[Deterministic synthetic generator] --> R[Local raw CSV zone]
    R -. Phase 2 .-> E[Python extract and validate]
    E -. Phase 2 .-> T[Transform and quarantine]
    T -. Phase 2/3 .-> P[(PostgreSQL warehouse)]
    P -. Phase 5 .-> Q[SQL analytics]
    Q -. Phase 5 .-> D[Reports or dashboard]

    S3[(AWS S3 raw zone)] -. Phase 6, approval required .-> E
    SSM[AWS Parameter Store] -. Phase 6 .-> E
```

The local raw directories deliberately mirror the future S3 prefixes:
`raw`, `processed`, and `quarantine`. The extract layer will use a storage
adapter so local files and S3 objects feed the same validation contract.

## Warehouse ER diagram

```mermaid
erDiagram
    DIM_CUSTOMERS ||--o{ FACT_SALES : "customer_key"
    DIM_PRODUCTS ||--o{ FACT_SALES : "product_key"
    DIM_DATES ||--o{ FACT_SALES : "order_date_key"
    PIPELINE_RUNS ||--o{ PROCESSED_SOURCE_FILES : "run_id"
    PIPELINE_RUNS ||--o{ REJECTED_RECORDS : "run_id"
    PIPELINE_RUNS ||--o{ DATA_QUALITY_RESULTS : "run_id"

    DIM_CUSTOMERS {
        bigint customer_key PK
        text customer_id UK
        text email
        text customer_status
    }
    DIM_PRODUCTS {
        bigint product_key PK
        text product_id UK
        text category
        numeric current_unit_price
    }
    DIM_DATES {
        integer date_key PK
        date full_date UK
        smallint month_number
        smallint year_number
    }
    FACT_SALES {
        bigint sales_key PK
        text order_item_id UK
        text order_id
        bigint customer_key FK
        bigint product_key FK
        integer order_date_key FK
        numeric net_line_amount
    }
    PIPELINE_RUNS {
        bigint run_id PK
        text batch_id UK
        text status
    }
    PROCESSED_SOURCE_FILES {
        bigint file_id PK
        bigint run_id FK
        text source_uri
        text content_checksum
    }
    REJECTED_RECORDS {
        bigint rejection_id PK
        bigint run_id FK
        jsonb raw_payload
    }
    DATA_QUALITY_RESULTS {
        bigint quality_result_id PK
        bigint run_id FK
        text check_name
        text status
    }
```

### Design decisions

- `fact_sales` has one row per order item, so revenue can be aggregated by
  customer, product, category, or date without mixing grains.
- Source IDs are natural keys used for idempotent upserts. Sequential `bigint`
  identity columns are compact surrogate keys used in joins.
- Monetary values use exact `numeric`, and timestamps use `timestamptz`.
- Every foreign key used for joins has an index. A composite status/date index
  supports time-window filtering by order status.
- Operational tables are separate from the analytical star schema so pipeline
  observability does not pollute business queries.
