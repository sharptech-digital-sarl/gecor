"""Vérifie l'intégrité du catalogue des permissions et des rôles par défaut."""

from __future__ import annotations

import pytest


def test_permissions_catalog_unique_keys():
    from app.core.permissions import PERMISSIONS_CATALOG

    keys = [item["key"] for item in PERMISSIONS_CATALOG]
    assert len(keys) == len(set(keys)), "Doublons dans le catalogue des permissions"


def test_permissions_catalog_has_label_and_key():
    from app.core.permissions import PERMISSIONS_CATALOG

    for entry in PERMISSIONS_CATALOG:
        assert "key" in entry and entry["key"], f"Entrée sans key : {entry}"
        assert "label" in entry and entry["label"], f"Entrée sans label : {entry}"
        assert isinstance(entry["key"], str)
        assert "." in entry["key"], f"Clé attendue au format `domain.action` : {entry['key']}"


def test_default_role_permissions_only_use_known_keys():
    from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, PERMISSIONS_CATALOG

    known = {item["key"] for item in PERMISSIONS_CATALOG} | {"mail.workflow.all"}
    for role, perms in DEFAULT_ROLE_PERMISSIONS.items():
        for perm in perms:
            assert perm in known, f"Rôle {role!r} contient la permission inconnue {perm!r}"


def test_master_role_has_all_permissions():
    """Le master doit avoir l'intégralité du catalogue."""
    from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, PERMISSIONS_CATALOG

    catalog_keys = {item["key"] for item in PERMISSIONS_CATALOG}
    master = set(DEFAULT_ROLE_PERMISSIONS["master"])
    assert catalog_keys.issubset(master), (
        f"Permissions manquantes pour master : {catalog_keys - master}"
    )


@pytest.mark.parametrize("role", ["director", "secretary", "analyst", "receptionist", "guest"])
def test_default_role_has_settings_self(role: str):
    from app.core.permissions import DEFAULT_ROLE_PERMISSIONS

    assert "settings.self" in DEFAULT_ROLE_PERMISSIONS[role], (
        f"Le rôle {role} doit pouvoir accéder à ses paramètres personnels"
    )
