"""Decode base64 / data-URL images and persist for visitor records (photo, ID copy)."""

from __future__ import annotations

import base64
import uuid

from fastapi import HTTPException

from app.services.storage_service import storage_service

_MAX_BYTES = 5 * 1024 * 1024


def _image_ext_from_magic(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data.startswith(b"RIFF") and b"WEBP" in data[:16]:
        return "webp"
    return "jpg"


async def save_visitor_base64_image(
    base64_input: str | None,
    visitor_id: uuid.UUID,
    storage_subdir: str,
    *,
    error_label: str = "Image",
) -> str | None:
    """
    Returns relative storage path, or None if input empty.
    Raises HTTPException 400 on invalid data or oversize.
    """
    if not base64_input or not str(base64_input).strip():
        return None
    raw = str(base64_input).strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {error_label} data")
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail=f"{error_label} too large (max 5MB)")
    ext = _image_ext_from_magic(data)
    fname = f"{visitor_id}.{ext}"
    return await storage_service.save_file(data, fname, storage_subdir)
