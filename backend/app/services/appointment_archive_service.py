"""Archivage logique des rendez-vous : hors listes opérationnelles, sans annulation de statut."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from app.models.appointment import Appointment
from app.services.appointment_cancellation_service import strip_external_calendar_events


async def archive_appointment_and_external_calendars(db: Session, appointment: Appointment) -> None:
    """
    Marque le RDV comme archivé et retire l’événement des calendriers externes si besoin.
    Ne commit pas.
    """
    if appointment.archived_at is not None:
        return
    appointment.archived_at = datetime.utcnow()
    await strip_external_calendar_events(db, appointment)
    db.add(appointment)


def load_appointment_for_archive(db: Session, appointment_id) -> Appointment | None:
    return (
        db.query(Appointment)
        .options(joinedload(Appointment.organizer))
        .filter(Appointment.id == appointment_id)
        .first()
    )
