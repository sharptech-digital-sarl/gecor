"""Surbrillance listes : éléments récents « destinés » à l’utilisateur connecté."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

RECENT_DESTINED_DAYS = 7


def _cutoff_utc() -> datetime:
    return datetime.utcnow() - timedelta(days=RECENT_DESTINED_DAYS)


def mail_highlight_destined(document: Any, user_id: Any) -> bool:
    """Courrier créé récemment et vous concernant : affecté à vous, ou déposé par vous sans affectation."""
    if document.created_at is None or document.created_at < _cutoff_utc():
        return False
    if document.assigned_to == user_id:
        return True
    if document.assigned_to is None and document.created_by == user_id:
        return True
    return False


def appointment_highlight_destined(appointment: Any, user_id: Any) -> bool:
    """RDV récent dont vous êtes la personne sollicitée (organisateur)."""
    if appointment.organizer_id != user_id:
        return False
    if appointment.created_at is None or appointment.created_at < _cutoff_utc():
        return False
    return True
