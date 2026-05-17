"""Smoke tests sur la configuration applicative."""

from __future__ import annotations


def test_settings_repr_masks_secrets():
    """Settings.__repr__ doit masquer les secrets (SECRET_KEY, DATABASE_URL, …)."""
    from app.core.config import settings

    rendered = repr(settings)
    assert "SECRET_KEY='***HIDDEN***'" in rendered
    assert "DATABASE_URL='***HIDDEN***'" in rendered
    assert settings.SECRET_KEY not in rendered, "Le secret est exposé dans repr(Settings)"


def test_project_name_is_gecor():
    from app.core.config import settings

    assert settings.PROJECT_NAME == "GECOR"


def test_cors_origins_is_list_of_strings():
    from app.core.config import settings

    assert isinstance(settings.CORS_ORIGINS, list)
    assert all(isinstance(o, str) for o in settings.CORS_ORIGINS)


def test_default_notification_locale_is_normalized():
    from app.core.config import settings

    assert settings.DEFAULT_NOTIFICATION_LOCALE in ("fr", "en")
