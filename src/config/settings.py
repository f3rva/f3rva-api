"""Application Settings & Environment Configuration with AWS SSM Support."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    import boto3
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def _fetch_ssm_parameters(env_key: str) -> dict[str, Any]:
    """Fetch all SSM parameters under /f3rva/{env}/ in a single batch call with decryption.

    Priority:
    - Skipped if in 'testing' environment or if ENABLE_SSM is explicitly set to false.
    - Only runs when in AWS (AWS_LAMBDA_FUNCTION_NAME / AWS_EXECUTION_ENV) or when ENABLE_SSM is 'true'.
    """
    if not HAS_BOTO3 or os.getenv("ENVIRONMENT") == "testing":
        return {}

    # Only fetch SSM if running in AWS Lambda or explicitly enabled for local testing
    is_in_aws = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME") or os.getenv("AWS_EXECUTION_ENV"))
    is_explicitly_enabled = os.getenv("ENABLE_SSM", "").lower() == "true"
    if not (is_in_aws or is_explicitly_enabled):
        return {}

    try:
        region = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))
        ssm = boto3.client("ssm", region_name=region)
        prefix = f"/f3rva/{env_key}/"
        paginator = ssm.get_paginator("get_parameters_by_path")
        params: dict[str, Any] = {}

        for page in paginator.paginate(Path=prefix, WithDecryption=True):
            for param in page.get("Parameters", []):
                raw_name = param["Name"].removeprefix(prefix).lower().replace("-", "_")
                # Normalize key names to match Settings attribute names
                if raw_name == "f3nation_api_key":
                    attr_name = "f3_nation_api_key"
                else:
                    attr_name = raw_name
                params[attr_name] = param["Value"]
        return params
    except Exception:
        return {}


class Settings(BaseSettings):
    """Application settings strictly externalized via AWS SSM Parameter Store and OS environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application Configuration
    app_name: str = Field(default="F3 RVA API", description="Application name displayed in OpenAPI and logs")
    app_version: str = Field(default="0.1.0", description="Fallback application version")
    environment: str = Field(default="development", description="Runtime environment name (development, testing, production)")
    debug: bool = Field(default=False, description="Debug mode flag")
    port: int = Field(default=8000, description="Server listen port")

    # Database Configuration
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


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings with SSM parameters prioritized over environment variables."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    env_key = "prod" if env in ("production", "prod") else "dev"

    # Fetch batch parameters from AWS SSM if enabled
    ssm_overrides = _fetch_ssm_parameters(env_key)

    # Instantiate Settings: keyword arguments (SSM) take highest priority,
    # falling back to OS environment variables / .env, and finally model defaults.
    return Settings(**ssm_overrides)
