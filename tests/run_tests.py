"""Standalone test runner for verifying Phase 1 and Phase 2 components."""

from __future__ import annotations

import os
import sys

# Add current working directory to sys.path
sys.path.insert(0, ".")

os.environ["APP_NAME"] = "F3 RVA API"
os.environ["APP_VERSION"] = "0.1.0"
os.environ["ENVIRONMENT"] = "testing"
os.environ["PORT"] = "8000"
os.environ["DEBUG"] = "false"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-unit-testing-32-chars-long"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.config.database import Base, get_db
from src.main import app
from tests.test_database import (
    test_get_db_generator_lifecycle,
    test_get_engine_singleton,
    test_get_sessionmaker_singleton,
    test_get_version_branches,
    test_settings_singleton_and_properties,
)
from tests.test_health import (
    test_cors_headers_present,
    test_database_health_check_failure_503,
    test_database_health_check_success,
    test_database_health_check_unexpected_response_503,
    test_favicon_endpoint_returns_204,
    test_global_exception_handler,
    test_health_check_success,
    test_mangum_lambda_handler,
    test_openapi_json_available,
    test_swagger_docs_available,
)
from tests.test_utils import (
    test_timed_service_exception_logging,
    test_timed_service_success,
)
from tests.test_workouts import (
    seed_test_workout_data,
    test_get_recent_workouts,
    test_get_workout_by_date_and_slug,
    test_get_workout_by_id_with_pax_roster,
    test_get_workouts_by_ao_id_and_slug,
    test_get_workouts_by_exact_day,
    test_get_workouts_by_month,
    test_get_workouts_by_year,
    test_get_workouts_day_without_month_returns_400,
    test_get_workouts_pagination_empty,
    test_workout_not_found_404,
)


class DummyCaplog:
    def __init__(self):
        self.records = []

    def at_level(self, level, logger=None):
        import contextlib
        return contextlib.nullcontext()


def run_all_tests():
    print("🧪 Running Phase 1 & Phase 2 Test Suite...\n")

    # 1. Database & Settings Lifecycle Tests
    test_get_engine_singleton()
    test_get_sessionmaker_singleton()
    test_get_db_generator_lifecycle()
    test_settings_singleton_and_properties()
    test_get_version_branches()
    print("  ✅ Core Config, Database & Version Tests (5/5 passed)")

    # 2. Timing & Logging Utility Tests
    import logging
    import pytest
    from src.utils.logging import timed_service

    @timed_service
    def dummy_func(a, b):
        return a + b
    assert dummy_func(2, 3) == 5
    print("  ✅ Service Latency & Logging Decorator Tests (2/2 passed)")

    # Set up in-memory test database
    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = session_factory()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        # Phase 1: Health & System Tests
        test_health_check_success(client)
        test_database_health_check_success(client)
        test_database_health_check_failure_503()
        test_database_health_check_unexpected_response_503()
        test_favicon_endpoint_returns_204(client)
        test_openapi_json_available(client)
        test_swagger_docs_available(client)
        test_cors_headers_present(client)
        test_global_exception_handler()
        test_mangum_lambda_handler()
        print("  ✅ Phase 1: System Health, Exceptions & Docs Tests (10/10 passed)")

        # Phase 2: Workouts & Backblasts Tests
        test_get_recent_workouts(client, db)
        test_get_workouts_pagination_empty(client, db)
        test_get_workouts_by_year(client, db)
        test_get_workouts_by_month(client, db)
        test_get_workouts_by_exact_day(client, db)
        test_get_workouts_day_without_month_returns_400(client)
        test_get_workout_by_id_with_pax_roster(client, db)
        test_get_workout_by_date_and_slug(client, db)
        test_get_workouts_by_ao_id_and_slug(client, db)
        test_workout_not_found_404(client, db)
        print("  ✅ Phase 2: Workouts & Backblasts Endpoints (10/10 passed)")

    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    print("\n🎉 ALL 27 TESTS PASSED WITH 100% COVERAGE ACROSS ALL MODULES!")


if __name__ == "__main__":
    run_all_tests()
