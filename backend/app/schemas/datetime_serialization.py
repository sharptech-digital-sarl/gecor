"""Sérialisation JSON des datetime : UTC explicite (suffixe Z) pour le frontend (évite l’interprétation locale erronée)."""

from __future__ import annotations

from datetime import datetime, timezone


def datetime_to_iso_utc_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        v = value.replace(tzinfo=timezone.utc)
    else:
        v = value.astimezone(timezone.utc)
    return v.isoformat().replace("+00:00", "Z")
