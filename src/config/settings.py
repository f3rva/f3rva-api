"""Application Settings & 12-Factor Environment Configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings strictly externalized via environment variables (zero hardcoded values)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application Configuration (Provided via .env / environment)
    app_name: str = Field(..., description="Application name displayed in OpenAPI and logs")
    app_version: str = Field(..., description="Fallback application version")
    environment: str = Field(..., description="Runtime environment name (development, testing, production)")
    debug: bool = Field(default=False, description="Debug mode flag")
    port: int = Field(..., description="Server listen port")

    # 12-Factor Database Configuration (Provided via .env / environment)
    database_url: str = Field(..., description="Full database connection URL")
    db_pool_pre_ping: bool = Field(default=True, description="Enable connection pre-ping")
    db_pool_recycle: int = Field(default=300, description="Connection recycle duration in seconds")
    db_connect_args: dict[str, Any] = Field(default_factory=dict, description="Custom database engine connection arguments")

    # Security & Admin Authentication
    jwt_secret_key: str = Field(
        default="change-me-in-production-jwt-secret-key-32-chars",
        description="JWT secret key for signing admin authentication tokens",
    )
    admin_username: str = Field(default="admin", description="Admin username for management endpoints")
    admin_password: str = Field(default="admin", description="Admin password for management endpoints")


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()
