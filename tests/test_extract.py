from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from pipeline.errors import ExtractionError
from pipeline.extract import extract_local_csvs
from pipeline.sample_data import generate_dataset


def test_extracts_multiple_files_and_metadata(tmp_path: Path) -> None:
    source = tmp_path / "raw"
    summary = generate_dataset(
        source, seed=9, customer_count=20, product_count=10, order_count=40
    )

    extracted = extract_local_csvs(source)

    assert set(extracted.frames) == {
        "customers",
        "products",
        "orders",
        "order_items",
        "payments",
    }
    assert extracted.rows_read == summary.total_records
    assert all(file.content_checksum for file in extracted.files)
    assert all(file.source_uri.startswith("file:") for file in extracted.files)


def test_missing_dataset_fails_with_clear_message(tmp_path: Path) -> None:
    source = tmp_path / "raw"
    generate_dataset(source, customer_count=5, product_count=5, order_count=10)
    for path in (source / "payments").glob("*.csv"):
        path.unlink()

    with pytest.raises(ExtractionError, match="No input files found for payments"):
        extract_local_csvs(source)


def test_missing_required_column_fails_before_transform(tmp_path: Path) -> None:
    source = tmp_path / "raw"
    generate_dataset(source, customer_count=5, product_count=5, order_count=10)
    customer_path = source / "customers" / "customers.csv"
    frame = pd.read_csv(customer_path).drop(columns=["customer_id"])
    frame.to_csv(customer_path, index=False)

    with pytest.raises(ExtractionError, match="Missing required columns.*customer_id"):
        extract_local_csvs(source)
