"""Tests for System Health, Database Connectivity, OpenAPI Docs, and CORS."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src.config.database import get_db
from src.main import app, handler


def test_health_check_success(client: TestClient) -> None:
    """Verify that the /health endpoint returns 200 OK and expected keys."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "f3rva-api"
    assert "version" in data
    assert "environment" in data


def test_database_health_check_success(client: TestClient) -> None:
    """Verify that /health/db executes SELECT 1 and reports connected."""
    response = client.get("/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "dialect" in data


def test_database_health_check_failure_503() -> None:
    """Verify that /health/db returns 503 and sanitized error when database connection fails."""
    mock_db = MagicMock()
    mock_db.execute.side_effect = OperationalError("connection refused", {}, None)

    def override_failing_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_failing_db
    with TestClient(app) as test_client:
        response = test_client.get("/health/db")
        assert response.status_code == 503
        data = response.json()
        assert data["errorCode"] == 5030
        assert "Database connection failed" in data["errorMessage"]
    app.dependency_overrides.clear()


def test_database_health_check_unexpected_response_503() -> None:
    """Verify that /health/db returns 503 when query returns an unexpected result."""
    mock_db = MagicMock()
    mock_db.execute.return_value.scalar.return_value = 0

    def override_bad_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_bad_db
    with TestClient(app) as test_client:
        response = test_client.get("/health/db")
        assert response.status_code == 503
        data = response.json()
        assert data["errorCode"] == 5031
    app.dependency_overrides.clear()


def test_favicon_endpoint_returns_204(client: TestClient) -> None:
    """Verify that /favicon.ico returns 204 No Content."""
    response = client.get("/favicon.ico")
    assert response.status_code == 204
    assert response.text == ""


def test_openapi_json_available(client: TestClient) -> None:
    """Verify that the OpenAPI JSON specification is generated."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "F3 RVA API"
    assert "/health" in schema["paths"]
    assert "/health/db" in schema["paths"]


def test_swagger_docs_available(client: TestClient) -> None:
    """Verify that Swagger UI documentation endpoint is accessible."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()


def test_cors_headers_present(client: TestClient) -> None:
    """Verify that CORS preflight and access-control headers are returned."""
    headers = {
        "Origin": "https://f3rva.org",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Content-Type",
    }
    response = client.options("/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://f3rva.org"


def test_global_exception_handler() -> None:
    """Verify that unhandled exceptions are caught and converted into structured 500 JSON."""

    @app.get("/test-error-500-trigger", include_in_schema=False)
    def trigger_unhandled_error():
        raise RuntimeError("Unexpected server crash")

    # raise_server_exceptions=False lets the global exception handler format the response
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test-error-500-trigger")
        assert response.status_code == 500
        data = response.json()
        assert data["errorCode"] == 5000
        assert data["errorMessage"] == "An internal server error occurred."


def test_mangum_lambda_handler() -> None:
    """Verify that the Mangum AWS Lambda handler entrypoint executes successfully."""
    event = {
        "version": "2.0",
        "routeKey": "GET /health",
        "rawPath": "/health",
        "rawQueryString": "",
        "headers": {"accept": "application/json"},
        "requestContext": {
            "http": {
                "method": "GET",
                "path": "/health",
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
                "userAgent": "pytest",
            }
        },
        "isBase64Encoded": False,
    }
    context = MagicMock()
    response = handler(event, context)
    assert response["statusCode"] == 200
