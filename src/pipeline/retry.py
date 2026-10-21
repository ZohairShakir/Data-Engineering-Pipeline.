"""Small retry helper for explicitly transient operations."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

LOGGER = logging.getLogger(__name__)


def with_retries[T](
    operation: Callable[[], T],
    *,
    retry_on: tuple[type[BaseException], ...],
    max_retries: int,
    base_delay_seconds: float = 1.0,
) -> T:
    """Retry transient exceptions with bounded exponential backoff."""
    attempt = 0
    while True:
        try:
            return operation()
        except retry_on as exc:
            if attempt >= max_retries:
                raise
            delay = base_delay_seconds * (2**attempt)
            attempt += 1
            LOGGER.warning(
                "transient operation failed; retrying",
                extra={"attempt": attempt, "delay_seconds": delay, "error": str(exc)},
            )
            time.sleep(delay)
