"""Typed contracts shared by ETL stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True, slots=True)
class SourceFileMetadata:
    dataset_name: str
    path: Path
    source_uri: str
    content_checksum: str
    file_size_bytes: int
    source_last_modified_at: datetime
    rows_read: int


@dataclass(slots=True)
class ExtractedData:
    frames: dict[str, pd.DataFrame]
    files: list[SourceFileMetadata]

    @property
    def rows_read(self) -> int:
        return sum(file.rows_read for file in self.files)


@dataclass(frozen=True, slots=True)
class RejectedRecord:
    dataset_name: str
    source_uri: str
    source_row_number: int | None
    record_identifier: str | None
    rejection_stage: str
    rejection_reason: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class QualityResult:
    check_name: str
    dataset_name: str
    status: str
    records_checked: int
    records_failed: int
    observed_value: float | int | None = None
    expected_value: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TransformedData:
    customers: pd.DataFrame
    products: pd.DataFrame
    dates: pd.DataFrame
    sales: pd.DataFrame
    rejected_records: list[RejectedRecord]
    quality_results: list[QualityResult]

    @property
    def rows_loaded(self) -> int:
        return len(self.sales)
