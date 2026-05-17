"""Tests unitaires des helpers métier (génération de référence, etc.)."""

from __future__ import annotations

import re


def test_generate_reference_number_format():
    """La référence doit ressembler à FPI-YYYYMMDD-XXXXXXXX (uppercase hex)."""
    from app.api.v1.mail import generate_reference_number

    ref = generate_reference_number()
    assert re.fullmatch(r"FPI-\d{8}-[0-9A-F]{8}", ref), f"Format inattendu : {ref}"


def test_generate_reference_numbers_are_unique():
    """Deux appels successifs ne doivent jamais collisionner (UUID4 derrière)."""
    from app.api.v1.mail import generate_reference_number

    refs = {generate_reference_number() for _ in range(50)}
    assert len(refs) == 50, "Collisions inattendues sur generate_reference_number"
