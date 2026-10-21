"""Validate, normalize, relate, and shape extracted data for analytics."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from pipeline.errors import TransformationError
from pipeline.models import ExtractedData, QualityResult, RejectedRecord, TransformedData

ORDER_STATUSES = {"completed", "cancelled", "returned", "pending"}
CUSTOMER_STATUSES = {"active", "inactive"}
PAYMENT_STATUSES = {"paid", "voided", "refunded", "pending"}
PAYMENT_METHODS = {"card", "upi", "net_banking", "wallet", "cash_on_delivery"}
EXPECTED_PAYMENT_STATUS = {
    "completed": "paid",
    "cancelled": "voided",
    "returned": "refunded",
    "pending": "pending",
}


def _json_value(value: Any) -> Any:
    if value is None or value is pd.NA or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


@dataclass(slots=True)
class _TransformContext:
    rejected: list[RejectedRecord] = field(default_factory=list)
    reason_counts: Counter[tuple[str, str]] = field(default_factory=Counter)

    def reject(
        self,
        frame: pd.DataFrame,
        mask: pd.Series,
        *,
        dataset_name: str,
        reason: str,
        identifier_column: str,
    ) -> pd.DataFrame:
        normalized_mask = mask.fillna(True).astype(bool)
        if not normalized_mask.any():
            return frame

        for _, row in frame.loc[normalized_mask].iterrows():
            identifier = row.get(identifier_column)
            payload = {
                column: _json_value(value)
                for column, value in row.items()
                if not column.startswith("_")
            }
            self.rejected.append(
                RejectedRecord(
                    dataset_name=dataset_name,
                    source_uri=str(row.get("_source_uri", "unknown")),
                    source_row_number=(
                        int(row["_source_row_number"])
                        if pd.notna(row.get("_source_row_number"))
                        else None
                    ),
                    record_identifier=(str(identifier) if pd.notna(identifier) else None),
                    rejection_stage="transform",
                    rejection_reason=reason,
                    raw_payload=payload,
                )
            )
            self.reason_counts[(dataset_name, reason)] += 1
        return frame.loc[~normalized_mask].copy()


def _normalize_strings(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for column in frame.columns:
        if column.startswith("_"):
            continue
        frame[column] = frame[column].astype("string").str.strip()
        frame[column] = frame[column].replace("", pd.NA)
    return frame


def _reject_missing(
    context: _TransformContext,
    frame: pd.DataFrame,
    *,
    dataset_name: str,
    required: tuple[str, ...],
    identifier_column: str,
) -> pd.DataFrame:
    mask = frame[list(required)].isna().any(axis=1)
    return context.reject(
        frame,
        mask,
        dataset_name=dataset_name,
        reason="missing_required_value",
        identifier_column=identifier_column,
    )


def _reject_duplicates(
    context: _TransformContext,
    frame: pd.DataFrame,
    *,
    dataset_name: str,
    key: str,
    identifier_column: str,
) -> pd.DataFrame:
    return context.reject(
        frame,
        frame.duplicated(key, keep="first"),
        dataset_name=dataset_name,
        reason=f"duplicate_{key}",
        identifier_column=identifier_column,
    )


def _customers(context: _TransformContext, source: pd.DataFrame) -> pd.DataFrame:
    frame = _normalize_strings(source)
    frame["customer_status"] = frame["customer_status"].str.lower()
    frame["country_code"] = frame["country_code"].str.upper()
    frame = _reject_missing(
        context,
        frame,
        dataset_name="customers",
        required=(
            "customer_id",
            "first_name",
            "last_name",
            "country_code",
            "registered_at",
            "customer_status",
        ),
        identifier_column="customer_id",
    )
    frame = context.reject(
        frame,
        ~frame["customer_status"].isin(CUSTOMER_STATUSES),
        dataset_name="customers",
        reason="invalid_customer_status",
        identifier_column="customer_id",
    )
    frame = context.reject(
        frame,
        frame["country_code"].str.len().ne(2),
        dataset_name="customers",
        reason="invalid_country_code",
        identifier_column="customer_id",
    )
    frame["registered_at"] = pd.to_datetime(frame["registered_at"], utc=True, errors="coerce")
    frame = context.reject(
        frame,
        frame["registered_at"].isna(),
        dataset_name="customers",
        reason="invalid_registered_at",
        identifier_column="customer_id",
    )
    return _reject_duplicates(
        context,
        frame,
        dataset_name="customers",
        key="customer_id",
        identifier_column="customer_id",
    )


def _products(context: _TransformContext, source: pd.DataFrame) -> pd.DataFrame:
    frame = _normalize_strings(source)
    frame["category"] = frame["category"].str.lower().str.replace(r"\s+", "_", regex=True)
    frame = _reject_missing(
        context,
        frame,
        dataset_name="products",
        required=("product_id", "product_name", "category", "unit_price", "is_active"),
        identifier_column="product_id",
    )
    frame["unit_price"] = pd.to_numeric(frame["unit_price"], errors="coerce").round(2)
    frame = context.reject(
        frame,
        frame["unit_price"].isna() | frame["unit_price"].lt(0),
        dataset_name="products",
        reason="invalid_unit_price",
        identifier_column="product_id",
    )
    normalized_boolean = frame["is_active"].str.lower().map(
        {"true": True, "false": False, "1": True, "0": False}
    )
    frame = context.reject(
        frame,
        normalized_boolean.isna(),
        dataset_name="products",
        reason="invalid_is_active",
        identifier_column="product_id",
    )
    frame["is_active"] = normalized_boolean.loc[frame.index].astype(bool)
    return _reject_duplicates(
        context,
        frame,
        dataset_name="products",
        key="product_id",
        identifier_column="product_id",
    )


def _orders(context: _TransformContext, source: pd.DataFrame) -> pd.DataFrame:
    frame = _normalize_strings(source)
    frame["order_status"] = frame["order_status"].str.lower()
    frame["currency"] = frame["currency"].str.upper()
    frame = _reject_missing(
        context,
        frame,
        dataset_name="orders",
        required=(
            "order_id",
            "customer_id",
            "ordered_at",
            "order_status",
            "order_total",
            "currency",
        ),
        identifier_column="order_id",
    )
    frame["ordered_at"] = pd.to_datetime(frame["ordered_at"], utc=True, errors="coerce")
    frame["order_total"] = pd.to_numeric(frame["order_total"], errors="coerce").round(2)
    frame = context.reject(
        frame,
        frame["ordered_at"].isna(),
        dataset_name="orders",
        reason="invalid_ordered_at",
        identifier_column="order_id",
    )
    frame = context.reject(
        frame,
        frame["order_total"].isna() | frame["order_total"].lt(0),
        dataset_name="orders",
        reason="invalid_order_total",
        identifier_column="order_id",
    )
    frame = context.reject(
        frame,
        ~frame["order_status"].isin(ORDER_STATUSES),
        dataset_name="orders",
        reason="invalid_order_status",
        identifier_column="order_id",
    )
    frame = context.reject(
        frame,
        frame["currency"].ne("INR"),
        dataset_name="orders",
        reason="unsupported_currency",
        identifier_column="order_id",
    )
    return _reject_duplicates(
        context,
        frame,
        dataset_name="orders",
        key="order_id",
        identifier_column="order_id",
    )


def _order_items(context: _TransformContext, source: pd.DataFrame) -> pd.DataFrame:
    frame = _normalize_strings(source)
    frame = _reject_missing(
        context,
        frame,
        dataset_name="order_items",
        required=(
            "order_item_id",
            "order_id",
            "product_id",
            "quantity",
            "unit_price",
            "line_amount",
        ),
        identifier_column="order_item_id",
    )
    for column in ("quantity", "unit_price", "line_amount"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    invalid_numeric = (
        frame[["quantity", "unit_price", "line_amount"]].isna().any(axis=1)
        | frame["quantity"].le(0)
        | frame["quantity"].mod(1).ne(0)
        | frame["unit_price"].lt(0)
        | frame["line_amount"].lt(0)
    )
    frame = context.reject(
        frame,
        invalid_numeric,
        dataset_name="order_items",
        reason="invalid_item_value",
        identifier_column="order_item_id",
    )
    frame["quantity"] = frame["quantity"].astype(int)
    frame["unit_price"] = frame["unit_price"].round(2)
    frame["line_amount"] = frame["line_amount"].round(2)
    calculated = (frame["quantity"] * frame["unit_price"]).round(2)
    frame = context.reject(
        frame,
        calculated.sub(frame["line_amount"]).abs().gt(0.01),
        dataset_name="order_items",
        reason="line_amount_mismatch",
        identifier_column="order_item_id",
    )
    return _reject_duplicates(
        context,
        frame,
        dataset_name="order_items",
        key="order_item_id",
        identifier_column="order_item_id",
    )


def _payments(context: _TransformContext, source: pd.DataFrame) -> pd.DataFrame:
    frame = _normalize_strings(source)
    frame["payment_method"] = frame["payment_method"].str.lower().str.replace(
        r"\s+", "_", regex=True
    )
    frame["payment_status"] = frame["payment_status"].str.lower()
    frame = _reject_missing(
        context,
        frame,
        dataset_name="payments",
        required=(
            "payment_id",
            "order_id",
            "payment_method",
            "payment_status",
            "payment_amount",
        ),
        identifier_column="payment_id",
    )
    frame["payment_amount"] = pd.to_numeric(frame["payment_amount"], errors="coerce").round(2)
    frame = context.reject(
        frame,
        frame["payment_amount"].isna() | frame["payment_amount"].lt(0),
        dataset_name="payments",
        reason="invalid_payment_amount",
        identifier_column="payment_id",
    )
    frame = context.reject(
        frame,
        ~frame["payment_method"].isin(PAYMENT_METHODS),
        dataset_name="payments",
        reason="invalid_payment_method",
        identifier_column="payment_id",
    )
    frame = context.reject(
        frame,
        ~frame["payment_status"].isin(PAYMENT_STATUSES),
        dataset_name="payments",
        reason="invalid_payment_status",
        identifier_column="payment_id",
    )
    frame["paid_at"] = pd.to_datetime(frame["paid_at"], utc=True, errors="coerce")
    needs_paid_at = frame["payment_status"].isin({"paid", "refunded"})
    frame = context.reject(
        frame,
        needs_paid_at & frame["paid_at"].isna(),
        dataset_name="payments",
        reason="missing_paid_at",
        identifier_column="payment_id",
    )
    frame = _reject_duplicates(
        context,
        frame,
        dataset_name="payments",
        key="payment_id",
        identifier_column="payment_id",
    )
    return _reject_duplicates(
        context,
        frame,
        dataset_name="payments",
        key="order_id",
        identifier_column="payment_id",
    )


def _quality_results(
    extracted: ExtractedData,
    valid_frames: dict[str, pd.DataFrame],
    context: _TransformContext,
) -> list[QualityResult]:
    results: list[QualityResult] = []
    for dataset_name, source in extracted.frames.items():
        rejected_count = sum(
            count
            for (rejected_dataset, _), count in context.reason_counts.items()
            if rejected_dataset == dataset_name
        )
        results.append(
            QualityResult(
                check_name="valid_row_ratio",
                dataset_name=dataset_name,
                status="passed" if rejected_count == 0 else "warning",
                records_checked=len(source),
                records_failed=rejected_count,
                observed_value=(
                    len(valid_frames[dataset_name]) / len(source) if len(source) else 0
                ),
                expected_value="1.0",
                details={"valid_rows": len(valid_frames[dataset_name])},
            )
        )

    for (dataset_name, reason), count in sorted(context.reason_counts.items()):
        results.append(
            QualityResult(
                check_name=reason,
                dataset_name=dataset_name,
                status="warning",
                records_checked=len(extracted.frames[dataset_name]),
                records_failed=count,
                observed_value=count,
                expected_value="0",
            )
        )
    return results


def transform_data(extracted: ExtractedData) -> TransformedData:
    """Transform extracted frames and quarantine every invalid source row."""
    context = _TransformContext()
    customers = _customers(context, extracted.frames["customers"])
    products = _products(context, extracted.frames["products"])
    orders = _orders(context, extracted.frames["orders"])
    items = _order_items(context, extracted.frames["order_items"])
    payments = _payments(context, extracted.frames["payments"])

    orders = context.reject(
        orders,
        ~orders["customer_id"].isin(customers["customer_id"]),
        dataset_name="orders",
        reason="unknown_customer_id",
        identifier_column="order_id",
    )
    items = context.reject(
        items,
        ~items["order_id"].isin(orders["order_id"]),
        dataset_name="order_items",
        reason="unknown_order_id",
        identifier_column="order_item_id",
    )
    items = context.reject(
        items,
        ~items["product_id"].isin(products["product_id"]),
        dataset_name="order_items",
        reason="unknown_product_id",
        identifier_column="order_item_id",
    )
    payments = context.reject(
        payments,
        ~payments["order_id"].isin(orders["order_id"]),
        dataset_name="payments",
        reason="unknown_order_id",
        identifier_column="payment_id",
    )

    payment_check = payments.merge(
        orders[["order_id", "order_status", "order_total"]], on="order_id", how="left"
    )
    expected_status = payment_check["order_status"].map(EXPECTED_PAYMENT_STATUS)
    paid_order = payment_check["order_status"].isin({"completed", "returned"})
    expected_amount = payment_check["order_total"].where(paid_order, 0)
    inconsistent_payment_ids = set(
        payment_check.loc[
            expected_status.ne(payment_check["payment_status"])
            | expected_amount.sub(payment_check["payment_amount"]).abs().gt(0.01),
            "payment_id",
        ]
    )
    payments = context.reject(
        payments,
        payments["payment_id"].isin(inconsistent_payment_ids),
        dataset_name="payments",
        reason="payment_order_mismatch",
        identifier_column="payment_id",
    )

    orders = context.reject(
        orders,
        ~orders["order_id"].isin(payments["order_id"]),
        dataset_name="orders",
        reason="missing_valid_payment",
        identifier_column="order_id",
    )
    items = context.reject(
        items,
        ~items["order_id"].isin(orders["order_id"]),
        dataset_name="order_items",
        reason="order_rejected",
        identifier_column="order_item_id",
    )
    payments = context.reject(
        payments,
        ~payments["order_id"].isin(orders["order_id"]),
        dataset_name="payments",
        reason="order_rejected",
        identifier_column="payment_id",
    )

    calculated_totals = items.groupby("order_id", as_index=False)["line_amount"].sum().rename(
        columns={"line_amount": "calculated_order_total"}
    )
    total_check = orders[["order_id", "order_total"]].merge(
        calculated_totals, on="order_id", how="left"
    )
    bad_total_order_ids = set(
        total_check.loc[
            total_check["calculated_order_total"].isna()
            | total_check["calculated_order_total"].sub(total_check["order_total"]).abs().gt(0.01),
            "order_id",
        ]
    )
    orders = context.reject(
        orders,
        orders["order_id"].isin(bad_total_order_ids),
        dataset_name="orders",
        reason="order_total_mismatch",
        identifier_column="order_id",
    )
    items = context.reject(
        items,
        ~items["order_id"].isin(orders["order_id"]),
        dataset_name="order_items",
        reason="order_rejected",
        identifier_column="order_item_id",
    )
    payments = context.reject(
        payments,
        ~payments["order_id"].isin(orders["order_id"]),
        dataset_name="payments",
        reason="order_rejected",
        identifier_column="payment_id",
    )

    if orders.empty or items.empty:
        raise TransformationError("No valid sales remain after validation")

    sales = (
        items.merge(
            orders[["order_id", "customer_id", "ordered_at", "order_status"]],
            on="order_id",
            how="inner",
        )
        .merge(payments[["order_id", "payment_method"]], on="order_id", how="inner")
        .copy()
    )
    sales["gross_line_amount"] = sales["line_amount"].round(2)
    sales["net_line_amount"] = sales["gross_line_amount"].where(
        sales["order_status"].eq("completed"), 0
    )
    sales.loc[sales["order_status"].eq("returned"), "net_line_amount"] = -sales.loc[
        sales["order_status"].eq("returned"), "gross_line_amount"
    ]
    sales["order_date_key"] = sales["ordered_at"].dt.strftime("%Y%m%d").astype(int)
    sales = sales.rename(
        columns={
            "ordered_at": "order_timestamp",
            "_source_uri": "source_file",
            "_source_last_modified_at": "source_updated_at",
        }
    )

    date_values = sales["order_timestamp"].dt.normalize().drop_duplicates().sort_values()
    dates = pd.DataFrame({"full_date": date_values.dt.date})
    date_series = pd.to_datetime(dates["full_date"])
    dates["date_key"] = date_series.dt.strftime("%Y%m%d").astype(int)
    dates["day_of_month"] = date_series.dt.day.astype(int)
    dates["month_number"] = date_series.dt.month.astype(int)
    dates["month_name"] = date_series.dt.month_name()
    dates["quarter_number"] = date_series.dt.quarter.astype(int)
    dates["year_number"] = date_series.dt.year.astype(int)
    dates["day_of_week"] = date_series.dt.isocalendar().day.astype(int)
    dates["day_name"] = date_series.dt.day_name()
    dates["is_weekend"] = dates["day_of_week"].isin({6, 7})

    customers_output = customers[
        [
            "customer_id",
            "first_name",
            "last_name",
            "email",
            "city",
            "state",
            "country_code",
            "registered_at",
            "customer_status",
        ]
    ].copy()
    products_output = products[
        ["product_id", "product_name", "category", "unit_price", "is_active"]
    ].rename(columns={"unit_price": "current_unit_price"})
    sales_output = sales[
        [
            "order_item_id",
            "order_id",
            "customer_id",
            "product_id",
            "order_date_key",
            "order_timestamp",
            "order_status",
            "payment_method",
            "quantity",
            "unit_price",
            "gross_line_amount",
            "net_line_amount",
            "source_file",
            "source_updated_at",
        ]
    ].copy()

    valid_frames = {
        "customers": customers_output,
        "products": products_output,
        "orders": orders,
        "order_items": items,
        "payments": payments,
    }
    return TransformedData(
        customers=customers_output,
        products=products_output,
        dates=dates,
        sales=sales_output,
        rejected_records=context.rejected,
        quality_results=_quality_results(extracted, valid_frames, context),
    )
