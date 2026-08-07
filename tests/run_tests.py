"""Standalone test runner for verifying Phase 1 foundation components."""

import os
import sys

# Add current working directory to sys.path
sys.path.insert(0, ".")

os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL_OVERRIDE"] = "sqlite:///:memory:"
os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-for-unit-testing-32-chars-long"

from src.config.settings import get_settings
from src.config.database import Base, get_db, get_engine, get_sessionmaker
from src.main import app, health_check


def test_settings_defaults():
    settings = get_settings()
    assert settings.app_name == "F3 RVA API"
    assert settings.environment == "testing"
    assert settings.get_database_url() == "sqlite:///:memory:"
    print("✅ test_settings_defaults passed")


def test_database_engine():
    engine = get_engine()
    assert engine is not None
    Base.metadata.create_all(bind=engine)
    session_factory = get_sessionmaker()
    session = session_factory()
    assert session is not None
    session.close()
    print("✅ test_database_engine passed")


def test_health_check_function():
    result = health_check()
    assert result["status"] == "healthy"
    assert result["service"] == "f3rva-api"
    assert result["version"] == "0.1.0"
    print("✅ test_health_check_function passed")


def test_fastapi_app_routes():
    route_paths = [route.path for route in app.routes]
    assert "/health" in route_paths
    assert "/docs" in route_paths
    assert "/openapi.json" in route_paths
    print("✅ test_fastapi_app_routes passed")


if __name__ == "__main__":
    print("🧪 Running Phase 1 Foundation Verification Tests...")
    test_settings_defaults()
    test_database_engine()
    test_health_check_function()
    test_fastapi_app_routes()
    print("🎉 All Phase 1 Verification Tests Passed Successfully!")
