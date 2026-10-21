"""Command-line entry point for repeatable pipeline operations."""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict
from pathlib import Path

from pipeline.config import ConfigurationError, Settings
from pipeline.logging_config import configure_logging
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
    return parser


def _check_database() -> None:
    from sqlalchemy import create_engine, text

    settings = Settings.from_environment()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
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
    except (ConfigurationError, OSError, RuntimeError, ValueError) as exc:
        LOGGER.error("command failed", extra={"command": args.command, "error": str(exc)})
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
