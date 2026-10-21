# Project progress

Last verified: October 21, 2026.

## Phase 1 — Architecture and environment

- [x] Repository structure and typed Python package
- [x] Docker Compose PostgreSQL 16 service
- [x] Star schema and operational metadata schema
- [x] Deterministic 47,622-row synthetic dataset generator
- [x] Source provenance and limitations

## Phase 2 — Basic ETL

- [x] Multi-file local CSV discovery and required-column checks
- [x] Data-type, null, duplicate, money, date, and relationship validation
- [x] Explicit quarantine records and per-run quality report
- [x] Dimension/fact transformation with documented revenue rules
- [x] SQLAlchemy batched transactional loading

## Phase 3 — Data modeling

- [x] Populate customer, product, date, and sales tables
- [x] Natural-key upserts and surrogate-key fact resolution
- [x] Primary/foreign keys, checks, and query indexes
- [x] Mermaid ER diagram and data dictionary

## Phase 4 — Reliability

- [x] SHA-256 file lineage and version-aware skip decisions
- [x] Idempotent forced reruns and changed-file incremental updates
- [x] Structured JSON logs, run history, and clear CLI exit codes
- [x] Transient database retry with exponential backoff
- [x] Unit, integration, idempotency, incremental, and recovery tests
- [x] Cron-ready wrapper and operations runbook
- [ ] Failure notifications (optional enhancement)

## Phase 5 — Analytics and UI

- [x] Ten versioned business analytics SQL queries
- [x] Results exported from the loaded warehouse to JSON and Markdown
- [x] Responsive React dashboard with category filtering and table sorting
- [x] Desktop/mobile browser QA and production dashboard container

## Phase 6 — AWS (approval required)

- [ ] Local/S3 storage interface and mocked AWS tests
- [ ] S3 raw, processed, and quarantine prefixes
- [ ] EC2 Docker runtime and schedule
- [ ] Least-privilege IAM instance role
- [ ] Systems Manager Parameter Store configuration
- [ ] CloudWatch logs/alarms
- [ ] Real end-to-end AWS verification and teardown

No phase 6 item has been claimed or provisioned.

## Phase 7 — Documentation

- [x] Recruiter-readable README and verified screenshot
- [x] Architecture, data dictionary, deployment plan, and runbook
- [x] Verified analytics sample output
- [x] Interview guide and honest resume bullets
- [x] GitHub Actions for Python, PostgreSQL, and dashboard gates

## Verification snapshot

- Python: 23 passed (18 unit + 5 PostgreSQL integration)
- Dashboard: 1 component/interaction test passed
- Ruff: passed
- TypeScript/Vite production build: passed
- Docker: PostgreSQL, pipeline, and dashboard images built
- Browser: 1536×1024 and 390×844; no console warnings/errors or framework
  overlay; category filtering, sorting, and mobile navigation exercised
