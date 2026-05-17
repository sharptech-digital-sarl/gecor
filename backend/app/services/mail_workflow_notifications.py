"""Notifications métier après transition courrier (in-app + e-mail optionnel)."""

from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.mail import MailDocument
from app.services.event_notifications import emit_in_app, user_ids_matching_any_permission


def _notify_targets(document: MailDocument, actor_id: UUID, prefer_assignee_only: bool) -> List[UUID]:
    """Utilisateurs à notifier, sans l’acteur."""
    out: List[UUID] = []
    if prefer_assignee_only:
        uid = document.assigned_to or document.created_by
        if uid and uid != actor_id:
            out.append(uid)
        return out
    if document.assigned_to and document.assigned_to != actor_id:
        out.append(document.assigned_to)
    if document.created_by and document.created_by != actor_id and document.created_by not in out:
        out.append(document.created_by)
    return out


async def notify_after_mail_transition(
    db: Session,
    document: MailDocument,
    action_key: str,
    actor_id: UUID,
) -> None:
    """
    Appeler après commit workflow sur le document (statut / assignation à jour).
    Centralise validation, mise en attente, compléments, rejet, affectation.
    """
    from app.tasks.notification_tasks import (
        send_mail_validation_required_task,
        send_mail_workflow_event_task,
    )

    ref = document.reference_number
    title = document.title

    if action_key == "assign" and document.assigned_to and document.assigned_to != actor_id:
        emit_in_app(
            db,
            [document.assigned_to],
            "Courrier affecté",
            f"{ref} — {title}",
            {"type": "mail_assigned", "document_id": str(document.id)},
        )
        return

    if action_key == "close":
        archivists = user_ids_matching_any_permission(
            db, "mail.workflow.archive", "mail.workflow.all"
        )
        targets = {a for a in archivists if a != actor_id}
        if targets:
            emit_in_app(
                db,
                targets,
                "Courrier à archiver",
                f"{ref} — {title}",
                {"type": "mail_ready_archive", "document_id": str(document.id)},
            )
        return

    if action_key == "submit_to_director":
        directors = user_ids_matching_any_permission(
            db, "mail.workflow.escalate_to_dg", "mail.workflow.all"
        )
        tid = {u for u in directors if u != actor_id}
        if tid:
            emit_in_app(
                db,
                tid,
                "Courrier à examiner (direction)",
                f"{ref} — {title}",
                {"type": "mail_pending_director", "document_id": str(document.id)},
            )
        return

    if action_key == "director_forward_dg":
        reviewers = user_ids_matching_any_permission(
            db, "mail.workflow.approve", "mail.workflow.all"
        )
        rid_set = {r for r in reviewers if r != actor_id}
        if rid_set:
            emit_in_app(
                db,
                rid_set,
                "Validation courrier requise (DG)",
                f"{ref} — {title}",
                {"type": "mail_validation", "document_id": str(document.id)},
            )
            send_mail_validation_required_task.delay(
                str(document.id), [str(x) for x in rid_set]
            )
        return

    if action_key == "submit_validation":
        reviewers = user_ids_matching_any_permission(
            db, "mail.workflow.approve", "mail.workflow.all"
        )
        rid_set = {r for r in reviewers if r != actor_id}
        if rid_set:
            emit_in_app(
                db,
                rid_set,
                "Validation courrier requise",
                f"{ref} — {title}",
                {"type": "mail_validation", "document_id": str(document.id)},
            )
            send_mail_validation_required_task.delay(
                str(document.id), [str(x) for x in rid_set]
            )
        return

    if action_key == "hold":
        targets = _notify_targets(document, actor_id, prefer_assignee_only=True)
        if targets:
            emit_in_app(
                db,
                targets,
                "Courrier en attente",
                f"{ref} — {title}",
                {"type": "mail_on_hold", "document_id": str(document.id)},
            )
            send_mail_workflow_event_task.delay(
                str(document.id), [str(x) for x in targets], "hold"
            )
        return

    if action_key == "request_changes":
        targets = _notify_targets(document, actor_id, prefer_assignee_only=True)
        if targets:
            emit_in_app(
                db,
                targets,
                "Compléments demandés",
                f"{ref} — {title}",
                {"type": "mail_request_changes", "document_id": str(document.id)},
            )
            send_mail_workflow_event_task.delay(
                str(document.id), [str(x) for x in targets], "request_changes"
            )
        return

    if action_key == "reject":
        targets = _notify_targets(document, actor_id, prefer_assignee_only=False)
        if targets:
            emit_in_app(
                db,
                targets,
                "Courrier rejeté",
                f"{ref} — {title}",
                {"type": "mail_rejected", "document_id": str(document.id)},
            )
            send_mail_workflow_event_task.delay(
                str(document.id), [str(x) for x in targets], "reject"
            )
