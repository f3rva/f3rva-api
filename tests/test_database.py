"""Unit Tests for Database Engine, Session Lifecycle, and Settings Configuration."""

from __future__ import annotations

import importlib.metadata
import subprocess
from unittest.mock import patch
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from src.config import database
from src.config.database import get_db, get_engine, get_sessionmaker
from src.config.settings import Settings, get_settings
from src.config.version import get_version


def test_get_engine_singleton() -> None:
    """Verify that get_engine creates an engine and returns the cached singleton on subsequent calls."""
    database._engine = None  # Reset singleton for testing
    engine1 = get_engine()
    assert isinstance(engine1, Engine)

    engine2 = get_engine()
    assert engine1 is engine2  # Ensure cached singleton is reused


def test_get_sessionmaker_singleton() -> None:
    """Verify that get_sessionmaker creates and reuses the sessionmaker singleton."""
    database._SessionLocal = None  # Reset singleton for testing
    session_factory1 = get_sessionmaker()
    assert isinstance(session_factory1, sessionmaker)

    session_factory2 = get_sessionmaker()
    assert session_factory1 is session_factory2


def test_get_db_generator_lifecycle() -> None:
    """Verify that get_db yields an active session and closes it cleanly upon exit."""
    db_gen = get_db()
    session = next(db_gen)
    assert session is not None

    # Verify session can execute queries against the configured database
    result = session.execute(text("SELECT 1")).scalar()
    assert result == 1

    # Trigger generator teardown (finally block)
    try:
        next(db_gen)
    except StopIteration:
        pass


def test_settings_singleton_and_properties() -> None:
    """Verify that get_settings loads required environment variables and caches the instance."""
    settings = get_settings()
    assert settings.app_name == "F3 RVA API"
    assert settings.app_version == "0.1.0"
    assert settings.environment == "testing"
    assert settings.database_url.startswith("sqlite")

    cached_settings = get_settings()
    assert settings is cached_settings


def test_get_version_branches() -> None:
    """Verify get_version across git describe, package metadata, and fallback defaults."""
    # 1. Live git describe
    v = get_version()
    assert v != ""

    # 2. Package metadata resolution
    with patch("subprocess.check_output", side_effect=Exception("no git")):
        with patch("importlib.metadata.version", return_value="1.2.3"):
            assert get_version() == "1.2.3"

    # 3. Fallback default
    with patch("subprocess.check_output", side_effect=Exception("no git")):
        with patch("importlib.metadata.version", side_effect=importlib.metadata.PackageNotFoundError):
            assert get_version() == "0.1.0"


def test_fetch_ssm_parameters_in_aws() -> None:
    """Verify _fetch_ssm_parameters fetches and maps parameters from AWS SSM Parameter Store."""
    from src.config.settings import _fetch_ssm_parameters
    from unittest.mock import MagicMock

    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {
            "Parameters": [
                {"Name": "/f3rva/dev/database_url", "Value": "mysql+pymysql://user:pass@db.f3rva.org/f3rva_bd"},
                {"Name": "/f3rva/dev/jwt_secret_key", "Value": "ssm-secret-key-32-chars-long"},
                {"Name": "/f3rva/dev/f3nation_api_key", "Value": "ssm-f3nation-key-123"},
            ]
        }
    ]
    mock_ssm = MagicMock()
    mock_ssm.get_paginator.return_value = mock_paginator

    with patch("os.getenv", side_effect=lambda k, default="": {
        "ENVIRONMENT": "development",
        "AWS_LAMBDA_FUNCTION_NAME": "f3rva-dev-api-lambda",
        "AWS_REGION": "us-east-1"
    }.get(k, default)):
        with patch("boto3.client", return_value=mock_ssm):
            params = _fetch_ssm_parameters("dev")
            assert params["database_url"] == "mysql+pymysql://user:pass@db.f3rva.org/f3rva_bd"
            assert params["jwt_secret_key"] == "ssm-secret-key-32-chars-long"
            assert params["f3_nation_api_key"] == "ssm-f3nation-key-123"


def test_fetch_ssm_parameters_error_graceful_fallback() -> None:
    """Verify _fetch_ssm_parameters returns empty dict gracefully on exception."""
    from src.config.settings import _fetch_ssm_parameters

    with patch("os.getenv", side_effect=lambda k, default="": {
        "ENVIRONMENT": "development",
        "ENABLE_SSM": "true"
    }.get(k, default)):
        with patch("boto3.client", side_effect=Exception("SSM client failure")):
            params = _fetch_ssm_parameters("dev")
            assert params == {}

