"""Application Settings & Environment Configuration with AWS SSM Support."""

from __future__ import annotations

from functools import lru_cache
import os
from typing import Any
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def _fetch_ssm_parameter(param_name: str) -> str | None:
    """Helper to fetch a single parameter value from AWS SSM Parameter Store."""
    if not HAS_BOTO3:
        return None
    try:
        ssm = boto3.client("ssm")
        response = ssm.get_parameter(Name=param_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception:
        return None


class Settings(BaseSettings):
    """Application settings strictly externalized via environment variables and AWS SSM Parameter Store."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application Configuration (Provided via .env / environment)
    app_name: str = Field(default="F3 RVA API", description="Application name displayed in OpenAPI and logs")
    app_version: str = Field(default="0.1.0", description="Fallback application version")
    environment: str = Field(default="development", description="Runtime environment name (development, testing, production)")
    debug: bool = Field(default=False, description="Debug mode flag")
    port: int = Field(default=8000, description="Server listen port")

    # Database Configuration (Provided via .env / environment / SSM)
    database_url: str = Field(
        default="mysql+pymysql://root:root@localhost:3306/f3rva_bd?charset=utf8mb4",
        description="Full database connection URL",
    )
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

    # F3 Nation Schedule Integration
    f3_nation_api_key: str | None = Field(default=None, description="API Key for api.f3nation.com")
    f3_region_id: str = Field(default="25240", description="F3 Nation Region ID for Richmond VA")
    client_id: str = Field(default="f3rva-website", description="Client identifier for upstream F3 Nation API")

    def resolve_ssm_secrets(self) -> None:
        """Resolve sensitive parameters from AWS SSM Parameter Store if not set via environment."""
        env = self.environment.lower()
        if env in ("production", "prod"):
            env_key = "prod"
        else:
            env_key = "dev"

        # If database_url is the default placeholder and running in AWS, try fetching from SSM
        if (self.database_url == "mysql+pymysql://root:root@localhost:3306/f3rva_bd?charset=utf8mb4" 
                and "AWS_LAMBDA_FUNCTION_NAME" in os.environ):
            val = _fetch_ssm_parameter(f"/f3rva/{env_key}/database_url")
            if val:
                self.database_url = val

        # JWT Secret Key
        if (self.jwt_secret_key == "change-me-in-production-jwt-secret-key-32-chars" 
                and "AWS_LAMBDA_FUNCTION_NAME" in os.environ):
            val = _fetch_ssm_parameter(f"/f3rva/{env_key}/jwt_secret_key")
            if val:
                self.jwt_secret_key = val

        # Admin Password
        if (self.admin_password == "admin" 
                and "AWS_LAMBDA_FUNCTION_NAME" in os.environ):
            val = _fetch_ssm_parameter(f"/f3rva/{env_key}/admin_password")
            if val:
                self.admin_password = val

        # F3 Nation API Key
        if not self.f3_nation_api_key:
            val = _fetch_ssm_parameter(f"/f3rva/{env_key}/f3nation_api_key")
            if val:
                self.f3_nation_api_key = val


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings with SSM resolution."""
    settings = Settings()
    settings.resolve_ssm_secrets()
    return settings
