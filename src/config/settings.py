"""Application Settings & Environment Configuration."""

from __future__ import annotations

from functools import lru_cache
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Application settings for local development and runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application
    app_name: str = "F3 RVA API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False
    port: int = 8000

    # Database Configuration (Existing Remote MySQL Host)
    db_host: str | None = None
    db_port: int = 3306
    db_user: str | None = None
    db_pass: str | None = None
    db_name: str = "f3rva_bd"
    db_pool_size: int = 5
    db_max_overflow: int = 2
    db_pool_recycle: int = 300
    db_pool_timeout: int = 10
    database_url_override: str | None = None

    def get_database_url_object(self) -> URL | str:
        """Construct a secure SQLAlchemy URL object handling special characters safely."""
        if self.database_url_override:
            return self.database_url_override

        host = self.db_host or os.getenv("DB_HOST")
        user = self.db_user or os.getenv("DB_USER")
        password = self.db_pass or os.getenv("DB_PASS")
        database = self.db_name or os.getenv("DB_NAME", "f3rva_bd")
        port = self.db_port or int(os.getenv("DB_PORT", "3306"))

        if host and user and password:
            # Use URL.create to safely escape special characters in passwords and prevent leakage
            return URL.create(
                drivername="mysql+pymysql",
                username=user,
                password=password,
                host=host,
                port=port,
                database=database,
                query={"charset": "utf8mb4"},
            )

        # Fallback to local SQLite in-memory for testing if no DB configured
        return "sqlite:///:memory:"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()
