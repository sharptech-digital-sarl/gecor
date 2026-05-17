import asyncio
import uuid

from datetime import datetime, timedelta
from typing import Literal, cast
from sqlalchemy.orm import Session, joinedload
from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.appointment import Appointment, AppointmentStatus
from app.models.mail import MailDocument
from app.services.notification_service import notification_service
from app.services.workflow_service import workflow_service
from app.models.password_reset_request import PasswordResetRequest, PasswordResetRequestStatus
from app.services.event_notifications import (
    emit_in_app,
    user_ids_matching_any_permission,
    user_ids_masters,
)


@celery_app.task(name="send_appointment_reminders")
def send_appointment_reminders_task():
    """Send appointment reminders 24 hours in advance"""
    db: Session = SessionLocal()
    try:
        target_time = datetime.utcnow() + timedelta(hours=24)
        start_range = target_time - timedelta(minutes=30)
        end_range = target_time + timedelta(minutes=30)

        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.start_time >= start_range,
                Appointment.start_time <= end_range,
                Appointment.reminder_sent == False,
                Appointment.status == AppointmentStatus.CONFIRMED,
                Appointment.archived_at.is_(None),
            )
            .all()
        )

        sent_count = 0
        for appointment in appointments:
            success = asyncio.run(notification_service.send_appointment_reminder(db, appointment))
            if success:
                appointment.reminder_sent = True
                appointment.reminder_sent_at = datetime.utcnow()
                sent_count += 1

        db.commit()
        return {"status": "success", "reminders_sent": sent_count}

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="send_public_booking_confirmation")
def send_public_booking_confirmation_task(appointment_id: str) -> dict:
    """E-mail de confirmation au visiteur après finalisation réception (RDV public ou interne, QR inline si dispo)."""
    db: Session = SessionLocal()
    try:
        aid = uuid.UUID(appointment_id)
        apt = (
            db.query(Appointment)
            .options(joinedload(Appointment.visitor), joinedload(Appointment.organizer))
            .filter(Appointment.id == aid)
            .first()
        )
        if not apt or not apt.visitor_email:
            return {"ok": False, "reason": "not_found_or_no_email"}
        ok = asyncio.run(notification_service.send_public_booking_confirmation(db, apt))
        if ok:
            row = db.query(Appointment).filter(Appointment.id == aid).first()
            if row:
                row.visitor_booking_email_sent_at = datetime.utcnow()
                db.commit()
        return {"ok": ok}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="send_mail_validation_required")
def send_mail_validation_required_task(document_id: str, recipient_user_ids: list[str]) -> dict:
    db: Session = SessionLocal()
    try:
        doc = db.query(MailDocument).filter(MailDocument.id == uuid.UUID(document_id)).first()
        if not doc:
            return {"ok": False, "reason": "document_not_found"}
        uids = [uuid.UUID(x) for x in recipient_user_ids]
        sent = asyncio.run(
            notification_service.send_mail_validation_required_emails(db, doc, uids)
        )
        return {"ok": True, "sent": sent}
    finally:
        db.close()


@celery_app.task(name="send_mail_workflow_event")
def send_mail_workflow_event_task(
    document_id: str,
    recipient_user_ids: list[str],
    event: Literal["hold", "request_changes", "reject"],
) -> dict:
    db: Session = SessionLocal()
    try:
        doc = db.query(MailDocument).filter(MailDocument.id == uuid.UUID(document_id)).first()
        if not doc:
            return {"ok": False, "reason": "document_not_found"}
        uids = [uuid.UUID(x) for x in recipient_user_ids]
        ev = cast(Literal["hold", "request_changes", "reject"], event)
        sent = asyncio.run(
            notification_service.send_mail_workflow_event_emails(db, doc, uids, ev)
        )
        return {"ok": True, "sent": sent}
    finally:
        db.close()


@celery_app.task(name="check_deadlines")
def check_deadlines_task():
    """Check for overdue documents and send alerts + notification in-app."""
    db: Session = SessionLocal()
    try:
        overdue_documents = workflow_service.check_deadlines(db)

        sent_count = 0
        for document in overdue_documents:
            success = asyncio.run(notification_service.send_deadline_alert(db, document))
            if success:
                sent_count += 1
            if document.assigned_to:
                recipients = [document.assigned_to]
            else:
                recipients = user_ids_matching_any_permission(
                    db, "mail.workflow.assign", "mail.workflow.all"
                )
            if recipients:
                emit_in_app(
                    db,
                    recipients,
                    "Courrier en retard",
                    f"{document.reference_number} — échéance dépassée.",
                    {"type": "mail_overdue", "document_id": str(document.id)},
                )

        return {"status": "success", "alerts_sent": sent_count}

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="remind_password_reset_requests")
def remind_password_reset_requests_task():
    """Rappel horaire aux masters pour les demandes « mot de passe oublié » encore en attente."""
    db: Session = SessionLocal()
    try:
        now = datetime.utcnow()
        pending = (
            db.query(PasswordResetRequest)
            .options(joinedload(PasswordResetRequest.user))
            .filter(PasswordResetRequest.status == PasswordResetRequestStatus.PENDING.value)
            .all()
        )
        master_ids = user_ids_masters(db)
        to_notify: list[PasswordResetRequest] = []
        for row in pending:
            last = row.last_master_reminder_at or row.created_at
            if (now - last) >= timedelta(hours=1):
                to_notify.append(row)

        for row in to_notify:
            row.last_master_reminder_at = now
        if to_notify:
            db.commit()

        count = 0
        if master_ids and to_notify:
            for row in to_notify:
                u = row.user
                if u:
                    account_line = f"Compte : {u.full_name} ({u.username})"
                else:
                    account_line = "Aucun compte associé à cet e-mail"
                body_txt = f"E-mail : {row.email_requested}. {account_line}."
                if row.requester_message:
                    body_txt += f" Message : {row.requester_message}"
                emit_in_app(
                    db,
                    master_ids,
                    "Rappel — réinitialisation mot de passe",
                    body_txt,
                    {
                        "type": "password_reset_request_reminder",
                        "request_id": str(row.id),
                    },
                )
                count += 1

        return {"status": "success", "reminders_sent": count}

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
