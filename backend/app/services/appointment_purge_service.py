"""Suppression définitive d’un rendez-vous (master / director)."""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.models.appointment import Appointment
from app.models.deletion_request import DeletionRequest, TARGET_APPOINTMENT
from app.services.appointment_cancellation_service import strip_external_calendar_events


async def permanently_delete_appointment(db: Session, appointment: Appointment) -> None:
    """
    Retire l’événement des calendriers externes, supprime les demandes de suppression liées,
    puis supprime le RDV (cascade ORM : visiteur, ODJ, tâches).
    Ne commit pas.
    """
    await strip_external_calendar_events(db, appointment)
    db.query(DeletionRequest).filter(
        DeletionRequest.target_type == TARGET_APPOINTMENT,
        DeletionRequest.target_id == appointment.id,
    ).delete(synchronize_session=False)
    db.delete(appointment)


def load_appointment_for_purge(db: Session, appointment_id) -> Appointment | None:
    return (
        db.query(Appointment)
        .options(joinedload(Appointment.organizer))
        .filter(Appointment.id == appointment_id)
        .first()
    )
