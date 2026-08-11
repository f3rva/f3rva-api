"""Structured logging and latency tracking decorators for service layer execution."""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("f3rva.services")

def timed_service[F: Callable[..., Any]](func: F) -> F:
    """Decorator to trace service call execution, recording start time, completion duration (ms), and errors.

    Emits structured DEBUG logs at entry and exit for precise latency troubleshooting in local dev & CloudWatch.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        service_name = func.__qualname__
        start_time = time.perf_counter()
        logger.debug("START service call: %s", service_name)
        try:
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(
                "END service call: %s | Duration: %.2fms",
                service_name,
                elapsed_ms,
            )
            return result
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(
                "FAIL service call: %s | Duration: %.2fms | Error: %s",
                service_name,
                elapsed_ms,
                exc,
            )
            raise

    return wrapper  # type: ignore[return-value]
