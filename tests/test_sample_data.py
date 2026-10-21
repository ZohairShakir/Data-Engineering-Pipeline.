from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from pipeline.sample_data import DatasetSummary, generate_dataset


@pytest.fixture
def generated_data(tmp_path: Path) -> tuple[Path, dict[str, object], DatasetSummary]:
    output = tmp_path / "raw"
    summary = generate_dataset(
        output,
        seed=7,
        customer_count=40,
        product_count=20,
        order_count=100,
    )
    return output, json.loads((output / "manifest.json").read_text()), summary


def _read_rows(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open(encoding="utf-8", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    return rows


def test_generator_is_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate_dataset(first, seed=11, customer_count=10, product_count=8, order_count=25)
    generate_dataset(second, seed=11, customer_count=10, product_count=8, order_count=25)

    first_files = sorted(path.relative_to(first) for path in first.rglob("*") if path.is_file())
    second_files = sorted(path.relative_to(second) for path in second.rglob("*") if path.is_file())
    assert first_files == second_files
    for relative_path in first_files:
        assert (first / relative_path).read_bytes() == (second / relative_path).read_bytes()


def test_generated_relationships_are_consistent(
    generated_data: tuple[Path, dict[str, object], DatasetSummary],
) -> None:
    output, _, _ = generated_data
    customer_ids = {
        row["customer_id"] for row in _read_rows([output / "customers" / "customers.csv"])
    }
    product_ids = {
        row["product_id"] for row in _read_rows([output / "products" / "products.csv"])
    }
    orders = _read_rows(sorted((output / "orders").glob("*.csv")))
    items = _read_rows(sorted((output / "order_items").glob("*.csv")))
    payments = _read_rows(sorted((output / "payments").glob("*.csv")))
    order_ids = {row["order_id"] for row in orders}

    assert all(row["customer_id"] in customer_ids for row in orders)
    assert all(row["order_id"] in order_ids for row in items)
    assert all(row["product_id"] in product_ids for row in items)
    assert all(row["order_id"] in order_ids for row in payments)
    assert len(payments) == len(orders)


def test_manifest_matches_generated_files(
    generated_data: tuple[Path, dict[str, object], DatasetSummary],
) -> None:
    output, manifest, summary = generated_data
    assert manifest["orders"] == 100
    assert manifest["customers"] == 40
    assert manifest["products"] == 20
    assert manifest["payments"] == 100
    assert manifest["total_records"] == (
        summary.customers
        + summary.products
        + summary.orders
        + summary.order_items
        + summary.payments
    )
    assert len(list((output / "orders").glob("orders_*.csv"))) == 12


@pytest.mark.parametrize(
    ("customers", "products", "orders"),
    [(0, 1, 1), (1, 0, 1), (1, 1, 0), (-1, 1, 1)],
)
def test_generator_rejects_non_positive_counts(
    tmp_path: Path, customers: int, products: int, orders: int
) -> None:
    with pytest.raises(ValueError, match="must all be positive"):
        generate_dataset(
            tmp_path / "invalid",
            customer_count=customers,
            product_count=products,
            order_count=orders,
        )


def test_generator_supports_small_catalog_and_preserves_unrelated_files(tmp_path: Path) -> None:
    output = tmp_path / "raw"
    generate_dataset(output, customer_count=1, product_count=1, order_count=3)
    note = output / "keep-me.txt"
    note.write_text("user-owned", encoding="utf-8")

    generate_dataset(output, customer_count=1, product_count=1, order_count=3)

    assert note.read_text(encoding="utf-8") == "user-owned"
