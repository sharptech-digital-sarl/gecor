"""Catégorie son (courrier / rendez-vous / autre) pour payload in-app et Web Push."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

SoundCategory = Literal["mail", "appointment", "other"]


def sound_category_for_payload(payload: Optional[Dict[str, Any]]) -> SoundCategory:
    if not payload:
        return "other"
    t = payload.get("type")
    target = payload.get("target")
    if t == "deletion_request":
        if target == "mail":
            return "mail"
        if target == "appointment":
            return "appointment"
        return "other"
    if isinstance(t, str):
        if t.startswith("mail_"):
            return "mail"
        if t == "check_in" or t == "appointment" or t.startswith("appointment_"):
            return "appointment"
    return "other"
