"""Tests for System Health, Database Connectivity, OpenAPI Docs, and CORS."""

from fastapi.testclient import TestClient


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
