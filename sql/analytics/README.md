# Analytics queries

This directory contains the ten portfolio analytics requested in the project
brief. Run all queries against the loaded PostgreSQL warehouse with:

```bash
.venv/bin/python -m pipeline analytics
```

The command exports machine-readable results to
`dashboard/public/analytics.json` and a recruiter-readable snapshot to
`docs/results/analytics-results.md`. These files are generated from the actual
loaded synthetic dataset; the SQL files remain the source of truth.
