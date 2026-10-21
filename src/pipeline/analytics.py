"""Execute versioned SQL analytics and export verified dashboard data."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, text

QUERY_FILES = (
    "01_total_revenue_by_month.sql",
    "02_top_products_by_revenue.sql",
    "03_highest_value_customers.sql",
    "04_average_order_value.sql",
    "05_category_performance.sql",
    "06_revenue_change_over_time.sql",
    "07_cancelled_order_percentage.sql",
    "08_repeat_customers.sql",
    "09_category_revenue_contribution.sql",
    "10_orders_processed_per_day.sql",
)

DASHBOARD_QUERY_FILES = (
    "01_category_monthly.sql",
    "02_category_metrics.sql",
    "03_product_performance.sql",
    "04_pipeline_status.sql",
)


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No rows returned._\n"
    columns = list(rows[0])
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return "\n".join(lines) + "\n"


def run_analytics(
    engine: Engine,
    *,
    sql_directory: Path,
    dashboard_sql_directory: Path = Path("sql/dashboard"),
    json_output: Path,
    markdown_output: Path,
) -> dict[str, Any]:
    results: dict[str, list[dict[str, Any]]] = {}
    with engine.connect() as connection:
        fact_count = int(
            connection.execute(text("select count(*) from warehouse.fact_sales")).scalar_one()
        )
        if fact_count == 0:
            raise RuntimeError("warehouse.fact_sales is empty; run the pipeline first")
        for filename in QUERY_FILES:
            query_path = sql_directory / filename
            query_name = query_path.stem[3:]
            rows = connection.execute(text(query_path.read_text(encoding="utf-8"))).mappings()
            results[query_name] = [
                {column: _json_value(value) for column, value in row.items()} for row in rows
            ]

        dashboard_results: dict[str, list[dict[str, Any]]] = {}
        for filename in DASHBOARD_QUERY_FILES:
            query_path = dashboard_sql_directory / filename
            query_name = query_path.stem[3:]
            rows = connection.execute(text(query_path.read_text(encoding="utf-8"))).mappings()
            dashboard_results[query_name] = [
                {column: _json_value(value) for column, value in row.items()} for row in rows
            ]

    payload: dict[str, Any] = {
        "metadata": {
            "generated_at": datetime.now(UTC).isoformat(),
            "dataset": "deterministic synthetic e-commerce data",
            "fact_rows": fact_count,
        },
        "results": results,
        "dashboard": dashboard_results,
    }
    json_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_lines = [
        "# Verified analytics results",
        "",
        "These results were generated from the loaded deterministic synthetic dataset.",
        "They are portfolio evidence, not claims about a real business.",
        "",
        f"Fact rows: **{fact_count:,}**",
        "",
    ]
    for filename in QUERY_FILES:
        query_name = Path(filename).stem[3:]
        title = query_name.replace("_", " ").title()
        rows = results[query_name]
        display_rows = rows[:12]
        markdown_lines.extend([f"## {title}", "", _markdown_table(display_rows)])
        if len(rows) > len(display_rows):
            markdown_lines.extend(
                [f"_Showing {len(display_rows)} of {len(rows)} rows._", ""]
            )
    markdown_output.write_text("\n".join(markdown_lines), encoding="utf-8")
    return payload
