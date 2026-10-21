# Interview guide

## The two-minute explanation

This project ingests five related synthetic commerce datasets split across 38
CSV files. The extractor validates contracts and captures file/row lineage. A
Pandas transformation layer normalizes values, rejects duplicates, invalid
money/dates, or inconsistent relationships, and preserves rejects in
quarantine. SQLAlchemy then upserts dimensions and order-item facts into a
PostgreSQL star schema in one transaction. SHA-256 metadata makes identical
reruns skippable, while stable natural keys make changed or forced runs
idempotent. Ten checked-in SQL queries produce verified JSON/Markdown results
used by a React dashboard.

## Questions to expect

### What is the fact-table grain?

One row per `order_item_id`. That lets revenue and units aggregate by product,
customer, order, category, or date without mixing order- and item-level rows.

### Why retain natural and surrogate keys?

Source natural keys identify records for deterministic upserts.
Warehouse-generated numeric surrogate keys make fact/dimension relationships
compact and independent of source identifier formatting.

### How is a rerun idempotent?

The pipeline first compares source URI/checksum pairs with successful processing
history for its version. Identical batches skip. Changed or forced batches use
`ON CONFLICT` upserts for customer, product, date, and order-item natural keys in
one transaction, so they update rather than duplicate.

### Is this truly incremental?

It is file-aware and key-upserting: identical files are skipped, changed files
are processed, and inserted/updated natural keys are merged. It is not change
data capture and does not reconcile deletions. Calling out that boundary is more
accurate than overstating the design.

### What happens to a bad row?

It is never silently dropped. The row is excluded from analytical facts,
written to the run's quarantine CSV, and inserted into `ops.rejected_records`
with source identity, stage, reason, and raw JSON. The quality report records
the check counts.

### Why use a transaction?

Dimensions, facts, source metadata, quality results, rejections, and the final
run state represent one logical load. Committing them together prevents facts
without dimensions or a `succeeded` marker for a partial write.

### Why PostgreSQL and a star schema?

PostgreSQL provides constraints, exact numerics, transactions, mature query
planning, and a realistic analytical SQL environment without managed-service
cost. The star schema makes business aggregations legible and teaches fact
grain, dimensions, and surrogate keys.

### Why not Airflow, Glue, Redshift, or Spark?

The current scale is 25,122 facts and one scheduled pipeline. Python, cron, and
PostgreSQL are easier to operate and explain. Those tools become reasonable
when orchestration dependencies, managed integration, warehouse concurrency, or
distributed volume create a measurable need.

### How is money handled?

Source values are validated as numeric and PostgreSQL stores exact
`numeric(p,2)` values. Net revenue rules are explicit: completed is positive,
returned is negative, and cancelled/pending is zero. The project avoids binary
floating-point storage for financial facts.

### What would you improve for production?

Add schema versioning and migrations, source contracts, deletion/CDC semantics,
SCD type 2 where history matters, object-level S3 idempotency, secret rotation,
metrics/alerts, backup/restore exercises, an API or BI semantic layer, and load
performance tests based on an actual service-level objective.

## Evidence to cite

- 47,622 deterministic input rows in 38 files
- 25,122 order-item facts and 365 dates
- 2,000 customers and 500 products
- 23 passing Python tests, including five live PostgreSQL integration tests
- one dashboard interaction test plus desktop/mobile browser QA
- ten business SQL queries with checked-in actual output
- zero rejected rows in the clean seed-42 reference run

Always describe these as local synthetic results. Do not say the pipeline runs
on AWS until the phase 6 verification checklist is actually complete.
