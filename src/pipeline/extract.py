"""Extract source CSV files and capture immutable source metadata."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from pipeline.errors import ExtractionError
from pipeline.models import ExtractedData, SourceFileMetadata

DATASET_PATTERNS: dict[str, str] = {
    "customers": "customers/*.csv",
    "products": "products/*.csv",
    "orders": "orders/*.csv",
    "order_items": "order_items/*.csv",
    "payments": "payments/*.csv",
}

REQUIRED_COLUMNS: dict[str, set[str]] = {
    "customers": {
        "customer_id",
        "first_name",
        "last_name",
        "email",
        "city",
        "state",
        "country_code",
        "registered_at",
        "customer_status",
    },
    "products": {
        "product_id",
        "product_name",
        "category",
        "unit_price",
        "is_active",
        "created_at",
    },
    "orders": {
        "order_id",
        "customer_id",
        "ordered_at",
        "order_status",
        "order_total",
        "currency",
    },
    "order_items": {
        "order_item_id",
        "order_id",
        "product_id",
        "quantity",
        "unit_price",
        "line_amount",
    },
    "payments": {
        "payment_id",
        "order_id",
        "payment_method",
        "payment_status",
        "payment_amount",
        "paid_at",
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path, dataset_name: str) -> pd.DataFrame:
    try:
        frame = pd.read_csv(
            path,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            on_bad_lines="error",
        )
    except (OSError, UnicodeError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ExtractionError(f"Unable to parse {dataset_name} file {path}: {exc}") from exc

    frame.columns = [str(column).strip().lower() for column in frame.columns]
    if len(frame.columns) != len(set(frame.columns)):
        raise ExtractionError(f"Duplicate column names in {dataset_name} file {path}")

    missing = sorted(REQUIRED_COLUMNS[dataset_name] - set(frame.columns))
    if missing:
        raise ExtractionError(
            f"Missing required columns in {dataset_name} file {path}: {', '.join(missing)}"
        )

    frame = frame[list(sorted(REQUIRED_COLUMNS[dataset_name]))].copy()
    frame["_source_uri"] = path.resolve().as_uri()
    frame["_source_row_number"] = range(2, len(frame) + 2)
    return frame


def extract_local_csvs(source_root: Path) -> ExtractedData:
    """Read all required local CSV datasets and return rows plus file metadata."""
    source_root = source_root.resolve()
    if not source_root.is_dir():
        raise ExtractionError(f"Source directory does not exist: {source_root}")

    frames: dict[str, pd.DataFrame] = {}
    files: list[SourceFileMetadata] = []

    for dataset_name, pattern in DATASET_PATTERNS.items():
        paths = sorted(path for path in source_root.glob(pattern) if path.is_file())
        if not paths:
            raise ExtractionError(
                f"No input files found for {dataset_name} using {source_root / pattern}"
            )

        dataset_frames: list[pd.DataFrame] = []
        for path in paths:
            frame = _read_csv(path, dataset_name)
            stat = path.stat()
            source_last_modified_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
            frame["_source_last_modified_at"] = source_last_modified_at
            files.append(
                SourceFileMetadata(
                    dataset_name=dataset_name,
                    path=path,
                    source_uri=path.resolve().as_uri(),
                    content_checksum=_sha256(path),
                    file_size_bytes=stat.st_size,
                    source_last_modified_at=source_last_modified_at,
                    rows_read=len(frame),
                )
            )
            dataset_frames.append(frame)

        frames[dataset_name] = pd.concat(dataset_frames, ignore_index=True)

    return ExtractedData(frames=frames, files=files)
