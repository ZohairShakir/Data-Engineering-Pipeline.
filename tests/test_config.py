from __future__ import annotations

import pytest

from pipeline.config import ConfigurationError, Settings


def test_settings_build_encoded_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_DB", "warehouse")
    monkeypatch.setenv("POSTGRES_USER", "etl user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p@ss/word")
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5433")

    settings = Settings.from_environment()

    assert settings.database_url == (
        "postgresql+psycopg://etl+user:p%40ss%2Fword@db:5433/warehouse"
    )
    assert settings.safe_database_target == "db:5433/warehouse"
    assert "p@ss" not in settings.safe_database_target


def test_settings_report_missing_required_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ConfigurationError, match="POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD"):
        Settings.from_environment()
