from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from pipeline.analytics import QUERY_FILES, run_analytics
from pipeline.config import Settings
from pipeline.errors import ExtractionError
from pipeline.runner import run_local_pipeline
from pipeline.sample_data import generate_dataset

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


@pytest.fixture
def clean_engine(database_url: str) -> Engine:
    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                truncate table
                    warehouse.fact_sales,
                    warehouse.dim_customers,
                    warehouse.dim_products,
                    warehouse.dim_dates,
                    ops.processed_source_files,
                    ops.rejected_records,
                    ops.data_quality_results,
                    ops.pipeline_runs
                restart identity cascade
                """
            )
        )
    try:
        yield engine
    finally:
        engine.dispose()


def test_pipeline_is_idempotent_and_skips_unchanged_files(
    clean_engine: Engine, tmp_path: Path
) -> None:
    source = tmp_path / "raw"
    summary = generate_dataset(
        source, seed=41, customer_count=40, product_count=20, order_count=120
    )
    kwargs = {
        "source_root": source,
        "processed_root": tmp_path / "processed",
        "quarantine_root": tmp_path / "quarantine",
    }

    first = run_local_pipeline(clean_engine, **kwargs)
    second = run_local_pipeline(clean_engine, **kwargs)
    forced = run_local_pipeline(clean_engine, force=True, **kwargs)

    expanded_summary = generate_dataset(
        source, seed=41, customer_count=40, product_count=20, order_count=130
    )
    incremental = run_local_pipeline(clean_engine, **kwargs)

    with clean_engine.connect() as connection:
        fact_count = connection.execute(
            text("select count(*) from warehouse.fact_sales")
        ).scalar_one()
        statuses = connection.execute(
            text("select status from ops.pipeline_runs order by run_id")
        ).scalars().all()
    assert first.status == "succeeded"
    assert second.status == "skipped"
    assert forced.status == "succeeded"
    assert summary.order_items < expanded_summary.order_items
    assert incremental.status == "succeeded"
    assert fact_count == expanded_summary.order_items
    assert statuses == ["succeeded", "skipped", "succeeded", "succeeded"]


def test_failed_extraction_is_recorded_and_clean_rerun_recovers(
    clean_engine: Engine, tmp_path: Path
) -> None:
    source = tmp_path / "raw"
    generate_dataset(source, seed=43, customer_count=20, product_count=10, order_count=40)
    product_path = source / "products" / "products.csv"
    products = pd.read_csv(product_path).drop(columns=["product_id"])
    products.to_csv(product_path, index=False)
    kwargs = {
        "source_root": source,
        "processed_root": tmp_path / "processed",
        "quarantine_root": tmp_path / "quarantine",
    }

    with pytest.raises(ExtractionError):
        run_local_pipeline(clean_engine, **kwargs)

    generate_dataset(source, seed=43, customer_count=20, product_count=10, order_count=40)
    recovered = run_local_pipeline(clean_engine, **kwargs)

    with clean_engine.connect() as connection:
        statuses = connection.execute(
            text("select status from ops.pipeline_runs order by run_id")
        ).scalars().all()
    assert statuses == ["failed", "succeeded"]
    assert recovered.status == "succeeded"


def test_analytics_exports_all_queries(clean_engine: Engine, tmp_path: Path) -> None:
    source = tmp_path / "raw"
    summary = generate_dataset(
        source, seed=47, customer_count=40, product_count=20, order_count=120
    )
    run_local_pipeline(
        clean_engine,
        source_root=source,
        processed_root=tmp_path / "processed",
        quarantine_root=tmp_path / "quarantine",
    )

    json_output = tmp_path / "analytics.json"
    markdown_output = tmp_path / "analytics.md"
    payload = run_analytics(
        clean_engine,
        sql_directory=Path("sql/analytics"),
        dashboard_sql_directory=Path("sql/dashboard"),
        json_output=json_output,
        markdown_output=markdown_output,
    )

    assert payload["metadata"]["fact_rows"] == summary.order_items
    assert set(payload["results"]) == {Path(name).stem[3:] for name in QUERY_FILES}
    assert set(payload["dashboard"]) == {
        "category_monthly",
        "category_metrics",
        "product_performance",
        "pipeline_status",
    }
    assert json_output.exists()
    assert "# Verified analytics results" in markdown_output.read_text(encoding="utf-8")
