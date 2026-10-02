"""Unit tests for utility helpers, structured logging, and latency tracing."""

from __future__ import annotations

import logging

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from src.config.settings import Settings
from src.utils.logging import timed_service
from src.utils.security import (
    create_access_token,
    decode_access_token,
    get_current_user,
)


def test_timed_service_success(caplog: pytest.LogCaptureFixture) -> None:
    """Verify timed_service logs START and END events with duration in milliseconds."""

    @timed_service
    def sample_service_call(x: int, y: int) -> int:
        return x + y

    with caplog.at_level(logging.DEBUG, logger="f3rva.services"):
        result = sample_service_call(3, 7)

    assert result == 10
    messages = [rec.message for rec in caplog.records]
    assert any("START service call: " in m for m in messages)
    assert any("END service call: " in m and "Duration:" in m for m in messages)


def test_timed_service_exception_logging(caplog: pytest.LogCaptureFixture) -> None:
    """Verify timed_service logs FAIL event with error details and re-raises exception."""

    @timed_service
    def failing_service_call() -> None:
        raise ValueError("Simulated service failure")

    with caplog.at_level(logging.DEBUG, logger="f3rva.services"):
        with pytest.raises(ValueError, match="Simulated service failure"):
            failing_service_call()

    messages = [rec.message for rec in caplog.records]
    assert any("START service call: " in m for m in messages)
    assert any("FAIL service call: " in m and "Error: Simulated service failure" in m for m in messages)


def test_create_and_decode_access_token_success() -> None:
    """Verify create_access_token and decode_access_token roundtrip successfully."""
    token = create_access_token(data={"sub": "admin_user", "role": "admin"})
    payload = decode_access_token(token)
    assert payload["sub"] == "admin_user"
    assert payload["role"] == "admin"
    assert "exp" in payload


def test_create_access_token_missing_jwt_secret_raises_500(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify create_access_token raises 500 when JWT_SECRET_KEY is not configured."""
    mock_settings = Settings(jwt_secret_key=None)
    monkeypatch.setattr("src.utils.security.get_settings", lambda: mock_settings)

    with pytest.raises(HTTPException) as exc_info:
        create_access_token({"sub": "admin", "role": "admin"})
    assert exc_info.value.status_code == 500
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail["errorCode"] == 5000
    assert "JWT secret key is not configured" in str(exc_info.value.detail["errorMessage"])


def test_decode_access_token_missing_jwt_secret_raises_500(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify decode_access_token raises 500 when JWT_SECRET_KEY is not configured."""
    mock_settings = Settings(jwt_secret_key=None)
    monkeypatch.setattr("src.utils.security.get_settings", lambda: mock_settings)

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token("some.bearer.token")
    assert exc_info.value.status_code == 500
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail["errorCode"] == 5000
    assert "JWT secret key is not configured" in str(exc_info.value.detail["errorMessage"])


def test_get_current_user_missing_credentials_raises_401() -> None:
    """Verify get_current_user raises 401 when Authorization credentials are missing."""
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(None)
    assert exc_info.value.status_code == 401
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail["errorCode"] == 4010
    assert "Missing Bearer Authorization header" in str(exc_info.value.detail["errorMessage"])


def test_get_current_user_missing_subject_raises_401() -> None:
    """Verify get_current_user raises 401 when token lacks 'sub' claim."""
    token = create_access_token(data={"role": "admin"})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(creds)
    assert exc_info.value.status_code == 401
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail["errorCode"] == 4010
    assert "Invalid token subject" in str(exc_info.value.detail["errorMessage"])


