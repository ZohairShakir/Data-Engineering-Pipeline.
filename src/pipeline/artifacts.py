"""Persist processed, quarantine, and data-quality artifacts for each run."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from pipeline.models import TransformedData


def write_run_artifacts(
    transformed: TransformedData,
    *,
    batch_id: str,
    processed_root: Path,
    quarantine_root: Path,
) -> dict[str, str]:
    processed_dir = processed_root / batch_id
    quarantine_dir = quarantine_root / batch_id
    processed_dir.mkdir(parents=True, exist_ok=False)
    quarantine_dir.mkdir(parents=True, exist_ok=False)

    datasets = {
        "dim_customers.csv": transformed.customers,
        "dim_products.csv": transformed.products,
        "dim_dates.csv": transformed.dates,
        "fact_sales.csv": transformed.sales,
    }
    for filename, frame in datasets.items():
        frame.to_csv(processed_dir / filename, index=False)

    rejection_columns = [
        "dataset_name",
        "source_uri",
        "source_row_number",
        "record_identifier",
        "rejection_stage",
        "rejection_reason",
        "raw_payload",
    ]
    rejected_rows = [
        {
            **asdict(record),
            "raw_payload": json.dumps(record.raw_payload, default=str, sort_keys=True),
        }
        for record in transformed.rejected_records
    ]
    pd.DataFrame(rejected_rows, columns=rejection_columns).to_csv(
        quarantine_dir / "rejected_records.csv", index=False
    )

    quality_payload = [asdict(result) for result in transformed.quality_results]
    quality_path = processed_dir / "data_quality_report.json"
    quality_path.write_text(
        json.dumps(quality_payload, indent=2, default=str, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "processed": str(processed_dir),
        "quarantine": str(quarantine_dir),
        "quality_report": str(quality_path),
    }
