"""
In-app (+ Web Push) emission for key domain events.

Les scénarios courrier détaillés (validation, attente, compléments, rejet, affectation)
sont regroupés dans ``mail_workflow_notifications.notify_after_mail_transition``.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.in_app_notification import InAppNotification
from app.models.role import Role
from app.models.user import User
from app.models.user_role import user_roles
from app.services.push_delivery import deliver_web_push_to_users
from app.services.notification_sse_hub import notification_sse_hub
from app.core.effective_permissions import user_has_any_permission
from app.core.permissions import DEFAULT_ROLE_PERMISSIONS


def emit_in_app(
    db: Session,
    user_ids: Iterable[UUID],
    title: str,
    body: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    uid_set = {u for u in user_ids if u is not None}
    if not uid_set:
        return
    for uid in uid_set:
        db.add(InAppNotification(user_id=uid, title=title, body=body, payload=payload))
    db.commit()
    deliver_web_push_to_users(db, uid_set, title, body, payload)
    for uid in uid_set:
        notification_sse_hub.publish(uid, {"type": "in_app_notification"})


def user_ids_masters(db: Session) -> List[UUID]:
    """Comptes actifs ayant le rôle master (notifications « mot de passe oublié »)."""
    master_rows = (
        db.query(User.id)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .filter(User.is_active.is_(True), func.lower(Role.name) == "master")
        .distinct()
        .all()
    )
    return [r[0] for r in master_rows]


def user_ids_matching_any_permission(db: Session, *permission_keys: str) -> List[UUID]:
    """
    Utilisateurs actifs ayant au moins une des permissions demandées.
    Réduit le périmètre par requêtes SQL (rôles master, JSONB, défauts par nom de rôle),
    puis vérifie avec la logique Python (alias mail.manage, multi-rôles).
    """
    keys = list(dict.fromkeys(permission_keys))
    if not keys:
        return []

    default_role_hits = [
        rn
        for rn, perms in DEFAULT_ROLE_PERMISSIONS.items()
        if any(pk in perms for pk in keys)
    ]
    default_role_lower = [r.lower() for r in default_role_hits]

    candidate_ids: set[UUID] = set()

    master_rows = (
        db.query(User.id)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .filter(User.is_active.is_(True), func.lower(Role.name) == "master")
        .distinct()
        .all()
    )
    candidate_ids.update(r[0] for r in master_rows)

    json_parts = [Role.permissions.contains([k]) for k in keys]
    json_parts.append(Role.permissions.contains(["mail.workflow.all"]))
    explicit_rows = (
        db.query(User.id)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .filter(User.is_active.is_(True))
        .filter(or_(*json_parts))
        .filter(func.jsonb_array_length(Role.permissions) > 0)
        .distinct()
        .all()
    )
    candidate_ids.update(r[0] for r in explicit_rows)

    if default_role_lower:
        default_rows = (
            db.query(User.id)
            .join(user_roles, user_roles.c.user_id == User.id)
            .join(Role, Role.id == user_roles.c.role_id)
            .filter(User.is_active.is_(True))
            .filter(func.lower(Role.name).in_(default_role_lower))
            .filter(func.jsonb_array_length(Role.permissions) == 0)
            .distinct()
            .all()
        )
        candidate_ids.update(r[0] for r in default_rows)

    if not candidate_ids:
        return []

    users = (
        db.query(User)
        .options(joinedload(User.roles))
        .filter(User.id.in_(candidate_ids), User.is_active.is_(True))
        .all()
    )
    return [u.id for u in users if user_has_any_permission(u, *keys)]


def user_ids_for_deletion_reviewers(db: Session) -> List[UUID]:
    rows = (
        db.query(User.id)
        .join(user_roles, user_roles.c.user_id == User.id)
        .join(Role, Role.id == user_roles.c.role_id)
        .filter(func.lower(Role.name).in_(["master", "director"]))
        .distinct()
        .all()
    )
    return [r[0] for r in rows]
