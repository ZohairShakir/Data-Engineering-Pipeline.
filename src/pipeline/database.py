"""Transactional PostgreSQL loading and operational metadata access."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict
from typing import Any

import pandas as pd
from sqlalchemy import Engine, create_engine, text

from pipeline.models import ExtractedData, SourceFileMetadata, TransformedData


def create_database_engine(database_url: str) -> Engine:
    """Create the application's bounded, health-checked connection pool."""
    return create_engine(
        database_url,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=1_800,
    )


def _value(value: Any) -> Any:
    if value is None or value is pd.NA or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if hasattr(value, "item"):
        return value.item()
    return value


def _frame_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {column: _value(value) for column, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _chunks(records: list[dict[str, Any]], size: int = 1_000) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(records), size):
        yield records[start : start + size]


class WarehouseRepository:
    """Keep warehouse writes atomic and metadata updates explicit."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def start_run(self, *, batch_id: str, source_name: str, pipeline_version: str) -> int:
        statement = text(
            """
            insert into ops.pipeline_runs (batch_id, pipeline_version, source_name, status)
            values (:batch_id, :pipeline_version, :source_name, 'running')
            returning run_id
            """
        )
        with self.engine.begin() as connection:
            return int(
                connection.execute(
                    statement,
                    {
                        "batch_id": batch_id,
                        "pipeline_version": pipeline_version,
                        "source_name": source_name,
                    },
                ).scalar_one()
            )

    def files_already_processed(
        self, files: list[SourceFileMetadata], *, pipeline_version: str
    ) -> bool:
        statement = text(
            """
            select exists (
                select 1
                from ops.processed_source_files f
                join ops.pipeline_runs r on r.run_id = f.run_id
                where f.source_uri = :source_uri
                  and f.content_checksum = :content_checksum
                  and r.pipeline_version = :pipeline_version
            )
            """
        )
        with self.engine.connect() as connection:
            return all(
                bool(
                    connection.execute(
                        statement,
                        {
                            "source_uri": source.source_uri,
                            "content_checksum": source.content_checksum,
                            "pipeline_version": pipeline_version,
                        },
                    ).scalar_one()
                )
                for source in files
            )

    def complete_skipped_run(self, run_id: int, extracted: ExtractedData) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    update ops.pipeline_runs
                    set status = 'skipped', completed_at = now(), rows_read = :rows_read
                    where run_id = :run_id
                    """
                ),
                {"run_id": run_id, "rows_read": extracted.rows_read},
            )

    def mark_run_failed(self, run_id: int, error_message: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    update ops.pipeline_runs
                    set status = 'failed', completed_at = now(), error_message = :error_message
                    where run_id = :run_id
                    """
                ),
                {"run_id": run_id, "error_message": error_message[:4_000]},
            )

    def _upsert_customers(self, connection: Any, frame: pd.DataFrame) -> None:
        statement = text(
            """
            insert into warehouse.dim_customers (
                customer_id, first_name, last_name, email, city, state,
                country_code, registered_at, customer_status
            ) values (
                :customer_id, :first_name, :last_name, :email, :city, :state,
                :country_code, :registered_at, :customer_status
            )
            on conflict (customer_id) do update set
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                email = excluded.email,
                city = excluded.city,
                state = excluded.state,
                country_code = excluded.country_code,
                registered_at = excluded.registered_at,
                customer_status = excluded.customer_status,
                updated_at = now()
            """
        )
        for chunk in _chunks(_frame_records(frame)):
            connection.execute(statement, chunk)

    def _upsert_products(self, connection: Any, frame: pd.DataFrame) -> None:
        statement = text(
            """
            insert into warehouse.dim_products (
                product_id, product_name, category, current_unit_price, is_active
            ) values (
                :product_id, :product_name, :category, :current_unit_price, :is_active
            )
            on conflict (product_id) do update set
                product_name = excluded.product_name,
                category = excluded.category,
                current_unit_price = excluded.current_unit_price,
                is_active = excluded.is_active,
                updated_at = now()
            """
        )
        for chunk in _chunks(_frame_records(frame)):
            connection.execute(statement, chunk)

    def _upsert_dates(self, connection: Any, frame: pd.DataFrame) -> None:
        statement = text(
            """
            insert into warehouse.dim_dates (
                date_key, full_date, day_of_month, month_number, month_name,
                quarter_number, year_number, day_of_week, day_name, is_weekend
            ) values (
                :date_key, :full_date, :day_of_month, :month_number, :month_name,
                :quarter_number, :year_number, :day_of_week, :day_name, :is_weekend
            )
            on conflict (date_key) do update set
                full_date = excluded.full_date,
                day_of_month = excluded.day_of_month,
                month_number = excluded.month_number,
                month_name = excluded.month_name,
                quarter_number = excluded.quarter_number,
                year_number = excluded.year_number,
                day_of_week = excluded.day_of_week,
                day_name = excluded.day_name,
                is_weekend = excluded.is_weekend
            """
        )
        for chunk in _chunks(_frame_records(frame)):
            connection.execute(statement, chunk)

    def _upsert_sales(self, connection: Any, frame: pd.DataFrame) -> None:
        customer_keys = dict(
            connection.execute(
                text("select customer_id, customer_key from warehouse.dim_customers")
            ).all()
        )
        product_keys = dict(
            connection.execute(
                text("select product_id, product_key from warehouse.dim_products")
            ).all()
        )
        sales = frame.copy()
        sales["customer_key"] = sales["customer_id"].map(customer_keys)
        sales["product_key"] = sales["product_id"].map(product_keys)
        if sales[["customer_key", "product_key"]].isna().any().any():
            raise ValueError("Unable to resolve warehouse surrogate keys for all sales rows")

        columns = [
            "order_item_id",
            "order_id",
            "customer_key",
            "product_key",
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
        statement = text(
            """
            insert into warehouse.fact_sales (
                order_item_id, order_id, customer_key, product_key, order_date_key,
                order_timestamp, order_status, payment_method, quantity, unit_price,
                gross_line_amount, net_line_amount, source_file, source_updated_at
            ) values (
                :order_item_id, :order_id, :customer_key, :product_key, :order_date_key,
                :order_timestamp, :order_status, :payment_method, :quantity, :unit_price,
                :gross_line_amount, :net_line_amount, :source_file, :source_updated_at
            )
            on conflict (order_item_id) do update set
                order_id = excluded.order_id,
                customer_key = excluded.customer_key,
                product_key = excluded.product_key,
                order_date_key = excluded.order_date_key,
                order_timestamp = excluded.order_timestamp,
                order_status = excluded.order_status,
                payment_method = excluded.payment_method,
                quantity = excluded.quantity,
                unit_price = excluded.unit_price,
                gross_line_amount = excluded.gross_line_amount,
                net_line_amount = excluded.net_line_amount,
                source_file = excluded.source_file,
                source_updated_at = excluded.source_updated_at,
                loaded_at = now()
            """
        )
        for chunk in _chunks(_frame_records(sales[columns])):
            connection.execute(statement, chunk)

    def _insert_rejections(self, connection: Any, run_id: int, data: TransformedData) -> None:
        statement = text(
            """
            insert into ops.rejected_records (
                run_id, dataset_name, source_uri, source_row_number, record_identifier,
                rejection_stage, rejection_reason, raw_payload
            ) values (
                :run_id, :dataset_name, :source_uri, :source_row_number, :record_identifier,
                :rejection_stage, :rejection_reason, cast(:raw_payload as jsonb)
            )
            """
        )
        records = [
            {
                **asdict(record),
                "run_id": run_id,
                "raw_payload": json.dumps(record.raw_payload, default=str, sort_keys=True),
            }
            for record in data.rejected_records
        ]
        for chunk in _chunks(records):
            connection.execute(statement, chunk)

    def _insert_quality_results(
        self, connection: Any, run_id: int, data: TransformedData
    ) -> None:
        statement = text(
            """
            insert into ops.data_quality_results (
                run_id, check_name, dataset_name, status, records_checked,
                records_failed, observed_value, expected_value, details
            ) values (
                :run_id, :check_name, :dataset_name, :status, :records_checked,
                :records_failed, :observed_value, :expected_value, cast(:details as jsonb)
            )
            """
        )
        records = [
            {
                **asdict(result),
                "run_id": run_id,
                "details": json.dumps(result.details, default=str, sort_keys=True),
            }
            for result in data.quality_results
        ]
        for chunk in _chunks(records):
            connection.execute(statement, chunk)

    def _insert_source_files(
        self,
        connection: Any,
        run_id: int,
        files: list[SourceFileMetadata],
        rejected_by_uri: Counter[str],
    ) -> None:
        statement = text(
            """
            insert into ops.processed_source_files (
                run_id, dataset_name, source_uri, content_checksum, file_size_bytes,
                source_last_modified_at, rows_read, rows_rejected
            ) values (
                :run_id, :dataset_name, :source_uri, :content_checksum, :file_size_bytes,
                :source_last_modified_at, :rows_read, :rows_rejected
            )
            on conflict (run_id, source_uri) do update set
                dataset_name = excluded.dataset_name,
                content_checksum = excluded.content_checksum,
                file_size_bytes = excluded.file_size_bytes,
                source_last_modified_at = excluded.source_last_modified_at,
                processed_at = now(),
                rows_read = excluded.rows_read,
                rows_rejected = excluded.rows_rejected
            """
        )
        records = [
            {
                "run_id": run_id,
                "dataset_name": source.dataset_name,
                "source_uri": source.source_uri,
                "content_checksum": source.content_checksum,
                "file_size_bytes": source.file_size_bytes,
                "source_last_modified_at": source.source_last_modified_at,
                "rows_read": source.rows_read,
                "rows_rejected": rejected_by_uri[source.source_uri],
            }
            for source in files
        ]
        for chunk in _chunks(records):
            connection.execute(statement, chunk)

    def load_transformed(
        self,
        *,
        run_id: int,
        extracted: ExtractedData,
        transformed: TransformedData,
    ) -> str:
        """Commit dimensions, facts, quality records, and run status atomically."""
        rejected_by_uri = Counter(record.source_uri for record in transformed.rejected_records)
        status = "partially_succeeded" if transformed.rejected_records else "succeeded"
        with self.engine.begin() as connection:
            connection.execute(text("set local statement_timeout = '60s'"))
            self._upsert_customers(connection, transformed.customers)
            self._upsert_products(connection, transformed.products)
            self._upsert_dates(connection, transformed.dates)
            self._upsert_sales(connection, transformed.sales)
            self._insert_rejections(connection, run_id, transformed)
            self._insert_quality_results(connection, run_id, transformed)
            self._insert_source_files(connection, run_id, extracted.files, rejected_by_uri)
            connection.execute(
                text(
                    """
                    update ops.pipeline_runs
                    set status = :status,
                        completed_at = now(),
                        rows_read = :rows_read,
                        rows_loaded = :rows_loaded,
                        rows_rejected = :rows_rejected
                    where run_id = :run_id
                    """
                ),
                {
                    "run_id": run_id,
                    "status": status,
                    "rows_read": extracted.rows_read,
                    "rows_loaded": transformed.rows_loaded,
                    "rows_rejected": len(transformed.rejected_records),
                },
            )
        return status

    def recent_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        statement = text(
            """
            select run_id, batch_id, pipeline_version, source_name, status,
                   started_at, completed_at, rows_read, rows_loaded, rows_rejected,
                   error_message
            from ops.pipeline_runs
            order by run_id desc
            limit :limit
            """
        )
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(statement, {"limit": limit}).mappings()]
