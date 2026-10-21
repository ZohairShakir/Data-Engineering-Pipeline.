"""End-to-end local pipeline orchestration."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine

from pipeline import __version__
from pipeline.artifacts import write_run_artifacts
from pipeline.database import WarehouseRepository
from pipeline.extract import extract_local_csvs
from pipeline.transform import transform_data

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PipelineResult:
    run_id: int
    batch_id: str
    status: str
    rows_read: int
    rows_loaded: int
    rows_rejected: int
    artifacts: dict[str, str]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def run_local_pipeline(
    engine: Engine,
    *,
    source_root: Path,
    processed_root: Path,
    quarantine_root: Path,
    force: bool = False,
) -> PipelineResult:
    batch_id = f"run-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    repository = WarehouseRepository(engine)
    run_id = repository.start_run(
        batch_id=batch_id,
        source_name=str(source_root.resolve()),
        pipeline_version=__version__,
    )
    try:
        extracted = extract_local_csvs(source_root)
        LOGGER.info(
            "source extraction complete",
            extra={"run_id": run_id, "batch_id": batch_id, "rows_read": extracted.rows_read},
        )
        if not force and repository.files_already_processed(
            extracted.files, pipeline_version=__version__
        ):
            repository.complete_skipped_run(run_id, extracted)
            return PipelineResult(
                run_id=run_id,
                batch_id=batch_id,
                status="skipped",
                rows_read=extracted.rows_read,
                rows_loaded=0,
                rows_rejected=0,
                artifacts={},
            )

        transformed = transform_data(extracted)
        artifacts = write_run_artifacts(
            transformed,
            batch_id=batch_id,
            processed_root=processed_root,
            quarantine_root=quarantine_root,
        )
        status = repository.load_transformed(
            run_id=run_id,
            extracted=extracted,
            transformed=transformed,
        )
        result = PipelineResult(
            run_id=run_id,
            batch_id=batch_id,
            status=status,
            rows_read=extracted.rows_read,
            rows_loaded=transformed.rows_loaded,
            rows_rejected=len(transformed.rejected_records),
            artifacts=artifacts,
        )
        LOGGER.info("pipeline run complete", extra=result.as_dict())
        return result
    except Exception as exc:
        try:
            repository.mark_run_failed(run_id, str(exc))
        except Exception:
            LOGGER.exception("unable to mark failed pipeline run", extra={"run_id": run_id})
        raise
