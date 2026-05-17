"""Configuration commune des tests GECOR.

Stratégie :

- Les tests « smoke » (sans base de données réelle) tournent sur sqlite en
  mémoire, avec ``OPENAPI_EXPORT=1`` pour empêcher ``Base.metadata.create_all``
  de s'exécuter à l'import (les modèles utilisent ``postgresql.UUID`` / ``JSONB``
  qui ne sont pas portables vers SQLite hors patchs lourds).
- Les variables d'environnement nécessaires (``SECRET_KEY``, ``DATABASE_URL``,
  …) sont posées **avant** tout import d'``app.*``.
- Pour les tests qui touchent une vraie base PostgreSQL (intégration), poser
  ``GECOR_TEST_DATABASE_URL`` dans l'environnement et marquer le test avec
  ``@pytest.mark.integration`` (skip auto sinon).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Backend root sur sys.path : utile quand pytest est lancé depuis la racine du dépôt
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Variables d'env *avant* tout import d'app.*
os.environ.setdefault("OPENAPI_EXPORT", "1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-min-32-chars-for-tests")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/0")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:3000"]')
os.environ.setdefault("MFA_REQUIRED_ROLES", "[]")
os.environ.setdefault(
    "GOOGLE_CALENDAR_SCOPES",
    '["openid","email","https://www.googleapis.com/auth/calendar.events"]',
)


@pytest.fixture(scope="session")
def fastapi_app():
    """Retourne l'instance FastAPI partagée par les tests smoke."""
    from app.main import app  # import différé après le set des env vars

    return app


@pytest.fixture()
def client(fastapi_app):
    """TestClient FastAPI prêt à l'emploi (utilise httpx en interne)."""
    from fastapi.testclient import TestClient

    with TestClient(fastapi_app) as c:
        yield c


def pytest_collection_modifyitems(config, items):
    """Skip auto des tests `integration` si GECOR_TEST_DATABASE_URL absent."""
    if os.environ.get("GECOR_TEST_DATABASE_URL"):
        return
    skip_integration = pytest.mark.skip(
        reason="Test d'intégration : définir GECOR_TEST_DATABASE_URL pour l'exécuter."
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
