from __future__ import annotations

import pytest

from pipeline.retry import with_retries


class TransientError(RuntimeError):
    pass


def test_retry_recovers_from_transient_failures() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TransientError("temporary")
        return "ok"

    result = with_retries(
        operation,
        retry_on=(TransientError,),
        max_retries=2,
        base_delay_seconds=0,
    )

    assert result == "ok"
    assert calls == 3


def test_retry_does_not_retry_non_transient_failure() -> None:
    with pytest.raises(ValueError, match="permanent"):
        with_retries(
            lambda: (_ for _ in ()).throw(ValueError("permanent")),
            retry_on=(TransientError,),
            max_retries=3,
            base_delay_seconds=0,
        )
