from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, text

from pipeline.config import Settings

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL")
    if value:
        return value
    required = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
    if all(os.getenv(name) for name in required):
        return Settings.from_environment().database_url
    pytest.skip("PostgreSQL test configuration is not available")


def test_expected_schemas_and_tables_exist(database_url: str) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    inspector = inspect(engine)
    try:
        assert set(inspector.get_table_names(schema="warehouse")) == {
            "dim_customers",
            "dim_dates",
            "dim_products",
            "fact_sales",
        }
        assert set(inspector.get_table_names(schema="ops")) == {
            "data_quality_results",
            "pipeline_runs",
            "processed_source_files",
            "rejected_records",
        }
    finally:
        engine.dispose()


def test_all_foreign_key_columns_have_leading_indexes(database_url: str) -> None:
    query = text(
        """
        select c.conrelid::regclass::text as table_name, a.attname as column_name
        from pg_constraint c
        join pg_attribute a
          on a.attrelid = c.conrelid
         and a.attnum = any(c.conkey)
        where c.contype = 'f'
          and c.connamespace in ('warehouse'::regnamespace, 'ops'::regnamespace)
          and not exists (
              select 1
              from pg_index i
              where i.indrelid = c.conrelid
                and i.indkey[0] = a.attnum
          )
        """
    )
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            missing_indexes = connection.execute(query).all()
        assert missing_indexes == []
    finally:
        engine.dispose()
