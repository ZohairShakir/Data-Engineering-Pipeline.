"""Command-line entry point for repeatable pipeline operations."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict
from pathlib import Path

from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError

from pipeline.analytics import run_analytics
from pipeline.config import ConfigurationError, Settings
from pipeline.database import WarehouseRepository, create_database_engine
from pipeline.errors import PipelineError
from pipeline.logging_config import configure_logging
from pipeline.retry import with_retries
from pipeline.runner import run_local_pipeline
from pipeline.sample_data import generate_dataset

LOGGER = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ecommerce-pipeline")
    parser.add_argument("--log-level", default="INFO")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate-data", help="generate synthetic source CSVs")
    generate.add_argument("--output", type=Path, default=Path("data/raw/local"))
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--customers", type=int, default=2_000)
    generate.add_argument("--products", type=int, default=500)
    generate.add_argument("--orders", type=int, default=10_000)

    subparsers.add_parser("check-db", help="verify PostgreSQL connectivity and schema")

    run = subparsers.add_parser("run", help="execute the local end-to-end ETL pipeline")
    run.add_argument("--source", type=Path, default=Path("data/raw/local"))
    run.add_argument("--processed", type=Path, default=Path("data/processed"))
    run.add_argument("--quarantine", type=Path, default=Path("data/quarantine"))
    run.add_argument("--max-retries", type=int, default=2)
    run.add_argument("--force", action="store_true", help="reprocess unchanged source files")

    analytics = subparsers.add_parser(
        "analytics", help="execute SQL analytics and export verified results"
    )
    analytics.add_argument("--sql-directory", type=Path, default=Path("sql/analytics"))
    analytics.add_argument(
        "--dashboard-sql-directory", type=Path, default=Path("sql/dashboard")
    )
    analytics.add_argument(
        "--json-output", type=Path, default=Path("dashboard/public/analytics.json")
    )
    analytics.add_argument(
        "--markdown-output",
        type=Path,
        default=Path("docs/results/analytics-results.md"),
    )

    runs = subparsers.add_parser("runs", help="show recent pipeline execution history")
    runs.add_argument("--limit", type=int, default=10)
    return parser


def _check_database() -> None:
    from sqlalchemy import text

    settings = Settings.from_environment()
    engine = create_database_engine(settings.database_url)
    with engine.connect() as connection:
        result = connection.execute(
            text(
                "select exists ("
                "select 1 from information_schema.tables "
                "where table_schema = 'warehouse' and table_name = 'fact_sales'"
                ")"
            )
        ).scalar_one()
    engine.dispose()
    if not result:
        raise RuntimeError("PostgreSQL is reachable, but warehouse.fact_sales is missing")
    LOGGER.info("database check passed", extra={"database": settings.safe_database_target})


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)
    try:
        if args.command == "generate-data":
            summary = generate_dataset(
                args.output,
                seed=args.seed,
                customer_count=args.customers,
                product_count=args.products,
                order_count=args.orders,
            )
            LOGGER.info(
                "synthetic dataset generated",
                extra={"output": str(args.output), **asdict(summary)},
            )
            print(json.dumps(asdict(summary), indent=2, sort_keys=True))
            return 0
        if args.command == "check-db":
            _check_database()
            return 0
        if args.command == "run":
            if args.max_retries < 0:
                raise ValueError("--max-retries cannot be negative")
            settings = Settings.from_environment()
            engine = create_database_engine(settings.database_url)
            try:
                result = with_retries(
                    lambda: run_local_pipeline(
                        engine,
                        source_root=args.source,
                        processed_root=args.processed,
                        quarantine_root=args.quarantine,
                        force=args.force,
                    ),
                    retry_on=(OperationalError, InterfaceError),
                    max_retries=args.max_retries,
                )
            finally:
                engine.dispose()
            print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
            return 0
        if args.command == "analytics":
            settings = Settings.from_environment()
            engine = create_database_engine(settings.database_url)
            try:
                payload = run_analytics(
                    engine,
                    sql_directory=args.sql_directory,
                    dashboard_sql_directory=args.dashboard_sql_directory,
                    json_output=args.json_output,
                    markdown_output=args.markdown_output,
                )
            finally:
                engine.dispose()
            print(json.dumps(payload["metadata"], indent=2, sort_keys=True))
            return 0
        if args.command == "runs":
            if args.limit <= 0:
                raise ValueError("--limit must be positive")
            settings = Settings.from_environment()
            engine = create_database_engine(settings.database_url)
            try:
                runs = WarehouseRepository(engine).recent_runs(args.limit)
            finally:
                engine.dispose()
            print(json.dumps(runs, indent=2, default=str, sort_keys=True))
            return 0
    except (
        ConfigurationError,
        OSError,
        PipelineError,
        RuntimeError,
        SQLAlchemyError,
        ValueError,
    ) as exc:
        LOGGER.error("command failed", extra={"command": args.command, "error": str(exc)})
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
