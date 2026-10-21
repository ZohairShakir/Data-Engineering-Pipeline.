select
    run_id,
    batch_id,
    status,
    rows_read,
    rows_loaded,
    rows_rejected,
    started_at,
    completed_at
from ops.pipeline_runs
order by run_id desc
limit 10;
