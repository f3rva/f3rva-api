"""Unit tests for utility helpers, structured logging, and latency tracing."""

from __future__ import annotations

import logging

import pytest

from src.utils.logging import timed_service


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
