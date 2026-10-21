# Operations and recovery runbook

## Command map

| Goal | Command |
|---|---|
| Create environment | `make setup` |
| Generate reference input | `make generate-data` |
| Start PostgreSQL | `make db-up` |
| Verify schema connectivity | `make db-check` |
| Run ETL | `make run` |
| Force an unchanged batch | `.venv/bin/python -m pipeline run --force` |
| Export analytics | `make analytics` |
| Inspect recent attempts | `make runs` |
| Run ETL + analytics | `./scripts/run_pipeline.sh` |
| Start dashboard | `make dashboard` |
| Stop services, keep data | `make db-down` |

CLI commands return `0` on success and `2` for handled configuration, source,
pipeline, database, or argument failures. Logs are one JSON object per line.

## First local run

```bash
cp .env.example .env
# Set a unique local-only POSTGRES_PASSWORD.
make setup
make dashboard-install
make generate-data
make db-up
make db-check
./scripts/run_pipeline.sh
```

Expected reference counts are 47,622 source rows, 25,122 fact rows, and zero
rejects. A different seed or size will produce different valid counts.

## Incremental behavior

An identical batch is marked `skipped` when every source URI/checksum was
previously loaded by the current pipeline version. Any changed file causes the
discovered batch to be revalidated, then dimensions and facts are upserted by
natural key in a transaction.

Use `--force` to exercise transformation and loading for unchanged content. A
forced rerun remains idempotent: unique source keys are updated, not duplicated.

This contract does not delete warehouse rows that disappeared from a later
source snapshot. Treat deletions as an explicit future design decision.

## Data-quality and quarantine artifacts

Each non-skipped attempt writes:

```text
data/processed/<batch-id>/dim_customers.csv
data/processed/<batch-id>/dim_products.csv
data/processed/<batch-id>/dim_dates.csv
data/processed/<batch-id>/fact_sales.csv
data/processed/<batch-id>/data_quality_report.json
data/quarantine/<batch-id>/rejected_records.csv
```

Generated artifacts are Git-ignored. Rejected rows also appear in
`ops.rejected_records`, and quality checks appear in
`ops.data_quality_results`.

## Failure recovery

1. Run `make runs` and inspect the latest `error_message`.
2. For source failures, verify all five dataset patterns and required columns.
3. Inspect the batch's quarantine/quality files when transformation completed.
4. For database failures, run `make db-check` and `docker compose logs postgres`.
5. Correct the source or dependency; do not manually change a failed run row.
6. Rerun `make run`. Natural-key upserts and the transaction make the retry safe.
7. Run `make analytics` only after a successful/partial run.
8. Confirm row counts and status with `make runs`.

The CLI retries only transient SQLAlchemy `OperationalError` and
`InterfaceError` failures. It does not retry malformed data or programming
errors because repetition cannot correct those conditions.

## Scheduling with cron

Use an absolute project path and redirect output to an access-controlled log.
Example daily schedule at 02:15 server-local time:

```cron
15 2 * * * cd /absolute/path/to/dataproject && ./scripts/run_pipeline.sh >> logs/cron.log 2>&1
```

Before enabling it:

- confirm `.env` is readable only by the intended OS user;
- run the exact command manually from a non-interactive shell;
- confirm the host timezone and source-data arrival time;
- configure log rotation;
- decide how nonzero exits will notify an operator.

Failure notification is not included. A simple first enhancement is a wrapper
that alerts only after the script exits nonzero, without including credentials
or raw customer rows in the message.

## PostgreSQL inspection

```sql
select run_id, batch_id, status, rows_read, rows_loaded, rows_rejected,
       started_at, completed_at, error_message
from ops.pipeline_runs
order by run_id desc
limit 10;

select count(*) from warehouse.fact_sales;

select check_name, dataset_name, status, records_checked, records_failed
from ops.data_quality_results
where run_id = (select max(run_id) from ops.pipeline_runs);
```

## Rebuilding a disposable local database

`docker compose down -v` deletes the local PostgreSQL volume. It is destructive
and should be used only when the stored warehouse is disposable and already
reproducible from raw inputs. Normal shutdown uses `make db-down`, which keeps
the volume.

After an intentional reset:

```bash
make db-up
make db-check
make run
make analytics
```

The custom PostgreSQL image applies `sql/schema.sql` only when initializing an
empty volume.
