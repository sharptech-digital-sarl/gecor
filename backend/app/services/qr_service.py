import base64
import io
import uuid

import qrcode
from fastapi import HTTPException

from app.services.storage_service import storage_service

QR_PREFIX = "APPT-"


def build_appointment_qr_payload(appointment_id: uuid.UUID) -> str:
    return f"{QR_PREFIX}{appointment_id}"


def build_appointment_qr_png_bytes(appointment_id: uuid.UUID) -> bytes:
    payload = build_appointment_qr_payload(appointment_id)
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(payload)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)
    return img_bytes.read()


def build_appointment_qr_base64(appointment_id: uuid.UUID) -> str:
    """PNG encodé en base64 (usage ponctuel, ex. e-mail si besoin sans lire le fichier)."""
    return base64.b64encode(build_appointment_qr_png_bytes(appointment_id)).decode("utf-8")


async def save_visitor_qr_png(appointment_id: uuid.UUID, visitor_id: uuid.UUID) -> str:
    """Écrit `qrcode/{visitor_id}.png` dans le storage ; retourne le chemin relatif."""
    png = build_appointment_qr_png_bytes(appointment_id)
    file_name = f"{visitor_id}.png"
    return await storage_service.save_file(png, file_name, "qrcode")


def parse_qr_payload_to_appointment_id(raw: str) -> uuid.UUID:
    value = (raw or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="QR payload is empty")
    if not value.startswith(QR_PREFIX):
        raise HTTPException(status_code=400, detail="Invalid QR payload format")
    raw_id = value[len(QR_PREFIX):]
    try:
        return uuid.UUID(raw_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid QR payload appointment id")
