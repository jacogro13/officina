# canonical: backend/settings_base.py v1
"""Settings base for every app (Blueprint v2, D4).

Each app subclasses it once and adds its own fields:

    class Settings(AppSettings):
        llm_base_url: str = ""

    @lru_cache
    def get_settings() -> Settings:
        return Settings()

Values come from environment variables (case-insensitive: `DB_HOST` → `db_host`).
Settings are validated when first built, so a missing or malformed variable stops
the container at boot instead of failing on the first request.

Database: set either `DATABASE_URL`, or the `DB_*` parts. The parts are the
production contract (`DB_USER=<app>_app`, see BLUEPRINT §7b). There is no default
password: a forgotten `DB_PASSWORD` is an error, never a silent weak fallback.
"""

from typing import Literal
from urllib.parse import quote

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    log_level: LogLevel = "INFO"

    database_url: str | None = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "postgres"
    db_password: SecretStr | None = None
    db_name: str | None = None

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _database_is_configured(self) -> "AppSettings":
        if self.database_url is None and (self.db_password is None or self.db_name is None):
            raise ValueError("Set DATABASE_URL, or both DB_PASSWORD and DB_NAME")
        return self

    def sqlalchemy_url(self, driver: str = "postgresql") -> str:
        """SQLAlchemy URL. `driver` (e.g. "postgresql+asyncpg") applies to the DB_* parts only."""
        if self.database_url is not None:
            return self.database_url
        assert self.db_password is not None  # guaranteed by _database_is_configured
        password = quote(self.db_password.get_secret_value(), safe="")
        user = quote(self.db_user, safe="")
        return f"{driver}://{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"
