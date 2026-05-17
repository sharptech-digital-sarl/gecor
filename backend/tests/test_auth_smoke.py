"""Smoke tests sur les endpoints d'authentification (sans base réelle)."""

from __future__ import annotations


def test_login_requires_credentials(client):
    """Sans corps, FastAPI doit refuser (422 ou 400)."""
    response = client.post("/api/v1/auth/login", json={})
    assert response.status_code in (400, 401, 422)


def test_protected_route_rejects_anonymous(client):
    """Un endpoint protégé doit retourner 401 sans token."""
    response = client.get("/api/v1/dashboard/kpi")
    assert response.status_code in (401, 403)


def test_mail_search_rejects_anonymous(client):
    """L'endpoint /mail/search doit exiger une authentification."""
    response = client.get("/api/v1/mail/search")
    assert response.status_code in (401, 403)


def test_mail_search_documented_in_openapi(client):
    schema = client.get("/openapi.json").json()
    op = schema["paths"]["/api/v1/mail/search"]["get"]
    assert "Mail" in " ".join(op.get("tags", []))
    params = {p["name"] for p in op.get("parameters", [])}
    expected = {
        "q",
        "status",
        "direction",
        "channel",
        "qualification",
        "tags",
        "sender_email",
        "assigned_to",
        "created_from",
        "created_to",
        "deadline_from",
        "deadline_to",
        "sort_by",
        "sort_dir",
        "skip",
        "limit",
        "include_facets",
        "archived",
        "overdue_only",
    }
    missing = expected - params
    assert not missing, f"Paramètres absents de l'OpenAPI : {missing}"
