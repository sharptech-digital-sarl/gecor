"""Permissions effectives : fusion des rôles, alias legacy (mail.manage), master = tout."""

from typing import Set

from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, PERMISSIONS_CATALOG
from app.models.user import User

_MASTER_ALL: Set[str] = {p["key"] for p in PERMISSIONS_CATALOG}


def _expand_manage_aliases(keys: Set[str]) -> Set[str]:
    out = set(keys)
    if "mail.manage" in keys:
        out.update(["mail.create", "mail.update", "mail.request_delete"])
    if "appointments.manage" in keys:
        out.update(["appointments.create", "appointments.update", "appointments.request_delete"])
    return out


def get_effective_permissions(user: User) -> Set[str]:
    if user.has_role("master"):
        return set(_MASTER_ALL)
    raw: Set[str] = set()
    for r in user.roles:
        if r.permissions:
            for p in r.permissions:
                raw.add(p)
    if raw:
        return _expand_manage_aliases(raw)
    for r in user.roles:
        name = r.name.lower()
        if name in DEFAULT_ROLE_PERMISSIONS:
            return _expand_manage_aliases(set(DEFAULT_ROLE_PERMISSIONS[name]))
    return set()


def user_has_permission(user: User, *permission_keys: str) -> bool:
    if not permission_keys:
        return True
    eff = get_effective_permissions(user)
    return all(k in eff for k in permission_keys)


def user_has_any_permission(user: User, *permission_keys: str) -> bool:
    if not permission_keys:
        return False
    eff = get_effective_permissions(user)
    return any(k in eff for k in permission_keys)
