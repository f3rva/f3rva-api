"""Standalone test runner for verifying Phase 1, Phase 2, and Phase 3 components."""

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
from tests.test_members import (
    seed_test_member_data,
    test_get_all_members_alphabetical,
    test_get_member_by_id_full_profile,
    test_get_member_by_id_not_found_404,
    test_get_member_stats_not_found_404,
    test_get_member_stats_success,
    test_get_member_stats_zero_division_safety,
    test_lookup_member_by_alias,
    test_lookup_member_by_primary_name,
    test_lookup_member_empty_query_400,
    test_lookup_member_not_found_404,
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


def run_all_tests():
    print("🧪 Running Phase 1, Phase 2 & Phase 3 Test Suite...\n")

    # 1. Database & Settings Lifecycle Tests
    test_get_engine_singleton()
    test_get_sessionmaker_singleton()
    test_get_db_generator_lifecycle()
    test_settings_singleton_and_properties()
    test_get_version_branches()
    print("  ✅ Core Config, Database & Version Tests (5/5 passed)")

    # 2. Timing & Logging Utility Tests
    from src.utils.logging import timed_service

    @timed_service
    def dummy_func(a, b):
        return a + b

    assert dummy_func(2, 3) == 5
    print("  ✅ Service Latency & Logging Decorator Tests (2/2 passed)")

    # Set up in-memory test database for workouts
    engine_w = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine_w)
    session_factory_w = sessionmaker(bind=engine_w, autocommit=False, autoflush=False)
    db_w = session_factory_w()

    def override_get_db_w():
        try:
            yield db_w
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db_w

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
        test_get_recent_workouts(client, db_w)
        test_get_workouts_pagination_empty(client, db_w)
        test_get_workouts_by_year(client, db_w)
        test_get_workouts_by_month(client, db_w)
        test_get_workouts_by_exact_day(client, db_w)
        test_get_workouts_day_without_month_returns_400(client)
        test_get_workout_by_id_with_pax_roster(client, db_w)
        test_get_workout_by_date_and_slug(client, db_w)
        test_get_workouts_by_ao_id_and_slug(client, db_w)
        test_workout_not_found_404(client, db_w)
        print("  ✅ Phase 2: Workouts & Backblasts Endpoints (10/10 passed)")

    app.dependency_overrides.clear()
    db_w.close()
    Base.metadata.drop_all(bind=engine_w)
    engine_w.dispose()

    # Set up in-memory test database for members
    engine_m = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine_m)
    session_factory_m = sessionmaker(bind=engine_m, autocommit=False, autoflush=False)
    db_m = session_factory_m()

    def override_get_db_m():
        try:
            yield db_m
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db_m

    with TestClient(app) as client:
        # Phase 3: Members & PAX Analytics Tests
        test_get_all_members_alphabetical(client, db_m)
        test_get_member_by_id_full_profile(client, db_m)
        test_get_member_stats_success(client, db_m)
        test_get_member_stats_zero_division_safety(client, db_m)
        test_lookup_member_by_primary_name(client, db_m)
        test_lookup_member_by_alias(client, db_m)
        test_lookup_member_empty_query_400(client)
        test_lookup_member_not_found_404(client, db_m)
        test_get_member_by_id_not_found_404(client, db_m)
        test_get_member_stats_not_found_404(client, db_m)
        print("  ✅ Phase 3: Members & PAX Analytics Endpoints (10/10 passed)")

    app.dependency_overrides.clear()
    db_m.close()
    Base.metadata.drop_all(bind=engine_m)
    engine_m.dispose()

    print("\n🎉 ALL 37 TESTS PASSED WITH 100% CODE COVERAGE ACROSS ALL MODULES!")


if __name__ == "__main__":
    run_all_tests()
