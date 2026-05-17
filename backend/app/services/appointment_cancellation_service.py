"""Annulation d’un rendez-vous : statut en base + suppression des événements calendrier externes."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models.appointment import Appointment, AppointmentStatus
from app.models.user import User
from app.services.google_calendar_service import google_calendar_service
from app.services.outlook_service import outlook_service

logger = logging.getLogger(__name__)


async def strip_external_calendar_events(db: Session, appointment: Appointment) -> None:
    """Supprime les événements Google / Outlook liés au RDV, sans changer le statut. Ne commit pas."""
    organizer: Optional[User] = appointment.organizer
    if not organizer:
        organizer = db.query(User).filter(User.id == appointment.organizer_id).first()

    if (
        organizer
        and appointment.google_event_id
        and google_calendar_service.is_configured()
        and organizer.google_refresh_token
    ):
        try:
            deleted = await google_calendar_service.delete_appointment_event(appointment, organizer)
            if deleted:
                appointment.google_event_id = None
        except Exception as exc:
            logger.warning("Google Calendar delete failed for appointment %s: %s", appointment.id, exc)

    if appointment.outlook_event_id and outlook_service.use_graph_api:
        try:
            deleted = await outlook_service.delete_graph_calendar_event(appointment)
            if deleted:
                appointment.outlook_event_id = None
                appointment.synced_with_outlook = False
        except Exception as exc:
            logger.warning("Outlook Graph delete failed for appointment %s: %s", appointment.id, exc)


async def cancel_appointment_and_external_calendars(db: Session, appointment: Appointment) -> None:
    """
    Passe le RDV en annulé et tente de retirer l’événement Google / Outlook si présent.
    Ne commit pas : l’appelant doit le faire.
    """
    if appointment.status == AppointmentStatus.CANCELLED:
        return
    if appointment.status in (AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW):
        raise ValueError("Appointment cannot be cancelled in current state")

    appointment.status = AppointmentStatus.CANCELLED
    await strip_external_calendar_events(db, appointment)
    db.add(appointment)


def load_appointment_for_cancellation(db: Session, appointment_id) -> Optional[Appointment]:
    return (
        db.query(Appointment)
        .options(joinedload(Appointment.organizer))
        .filter(Appointment.id == appointment_id)
        .first()
    )
