from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.extract import extract_local_csvs
from pipeline.sample_data import generate_dataset
from pipeline.transform import transform_data


def test_clean_generated_data_transforms_without_rejections(tmp_path: Path) -> None:
    source = tmp_path / "raw"
    summary = generate_dataset(
        source, seed=17, customer_count=30, product_count=15, order_count=80
    )

    transformed = transform_data(extract_local_csvs(source))

    assert len(transformed.sales) == summary.order_items
    assert len(transformed.customers) == summary.customers
    assert len(transformed.products) == summary.products
    assert transformed.rejected_records == []
    assert {result.status for result in transformed.quality_results} == {"passed"}
    returned = transformed.sales["order_status"].eq("returned")
    assert (transformed.sales.loc[returned, "net_line_amount"] <= 0).all()


def test_invalid_item_is_quarantined_and_dependencies_remain_consistent(tmp_path: Path) -> None:
    source = tmp_path / "raw"
    generate_dataset(source, seed=23, customer_count=30, product_count=15, order_count=80)
    item_path = sorted((source / "order_items").glob("*.csv"))[0]
    frame = pd.read_csv(item_path, dtype=str)
    invalid_item_id = frame.loc[0, "order_item_id"]
    invalid_order_id = frame.loc[0, "order_id"]
    frame.loc[0, "line_amount"] = "-20.00"
    frame.to_csv(item_path, index=False)

    transformed = transform_data(extract_local_csvs(source))

    reasons = {record.rejection_reason for record in transformed.rejected_records}
    assert "invalid_item_value" in reasons
    assert invalid_item_id not in set(transformed.sales["order_item_id"])
    assert invalid_order_id not in set(transformed.sales["order_id"])
    assert any(result.status == "warning" for result in transformed.quality_results)


def test_duplicate_natural_key_is_reported_not_silently_dropped(tmp_path: Path) -> None:
    source = tmp_path / "raw"
    generate_dataset(source, seed=31, customer_count=30, product_count=15, order_count=80)
    customer_path = source / "customers" / "customers.csv"
    frame = pd.read_csv(customer_path, dtype=str)
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    frame.to_csv(customer_path, index=False)

    transformed = transform_data(extract_local_csvs(source))

    duplicate_rejections = [
        record
        for record in transformed.rejected_records
        if record.rejection_reason == "duplicate_customer_id"
    ]
    assert len(duplicate_rejections) == 1
    assert len(transformed.customers) == 30
