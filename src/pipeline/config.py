"""Environment-based application configuration.

Local development reads normal environment variables (usually populated from
an ignored .env file by Docker Compose). A later AWS phase will add Parameter
Store resolution without changing the rest of the pipeline.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import quote_plus


class ConfigurationError(ValueError):
    """Raised when required application configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    log_level: str
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    database_url_override: str | None = None

    @classmethod
    def from_environment(cls) -> Settings:
        required = ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            names = ", ".join(missing)
            raise ConfigurationError(
                f"Missing required environment variables: {names}. "
                "Copy .env.example to .env and set local values."
            )

        port_value = os.getenv("POSTGRES_PORT", "5432")
        try:
            port = int(port_value)
        except ValueError as exc:
            raise ConfigurationError("POSTGRES_PORT must be an integer") from exc

        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
            postgres_port=port,
            postgres_db=os.environ["POSTGRES_DB"],
            postgres_user=os.environ["POSTGRES_USER"],
            postgres_password=os.environ["POSTGRES_PASSWORD"],
            database_url_override=os.getenv("DATABASE_URL"),
        )

    @property
    def database_url(self) -> str:
        if self.database_url_override:
            return self.database_url_override
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+psycopg://{user}:{password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def safe_database_target(self) -> str:
        """Return a log-safe database target that never contains credentials."""
        return f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
