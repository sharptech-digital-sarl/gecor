"""Smoke tests : santé de l'API et accessibilité de l'OpenAPI."""

from __future__ import annotations


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "gecor"


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "GECOR" in data["message"]
    assert "version" in data


def test_openapi_schema_is_served(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "GECOR API"
    # Routes critiques présentes
    paths = schema["paths"]
    assert "/health" in paths
    assert "/api/v1/auth/login" in paths
    assert "/api/v1/mail/search" in paths
    assert "/api/v1/dashboard/kpi" in paths


def test_docs_and_redoc_endpoints_load(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
