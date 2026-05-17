"""Email types for API schemas.

Pydantic's ``EmailStr`` / ``email-validator`` reject special-use TLDs such as
``.local`` (RFC 6762). Dev accounts like ``admin@fpi-connect.local`` must still
validate and serialize (e.g. ``GET /auth/me``).
"""
import re
from typing import Annotated

from pydantic import AfterValidator

# Loose syntax: local@domain — allows .local, .localhost, single-label hosts, etc.
_LOOSE_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")
_MAX_EMAIL_LEN = 254


def _validate_email_relaxed(value: str) -> str:
    v = value.strip()
    if not v:
        raise ValueError("email must not be empty")
    if len(v) > _MAX_EMAIL_LEN:
        raise ValueError("email is too long")
    if not _LOOSE_EMAIL_RE.match(v):
        raise ValueError("invalid email format")
    return v


RelaxedEmailStr = Annotated[str, AfterValidator(_validate_email_relaxed)]
