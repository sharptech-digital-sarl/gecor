import base64
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from app.schemas.email_types import RelaxedEmailStr
from datetime import datetime
from typing import List, Optional

from app.core.database import get_db
from app.models.role import Role
from app.models.user import User
from app.models.appointment import Appointment, AppointmentStatus, BookingSource, Visitor
from app.models.public_information_post import PublicInformationPost
from app.schemas.appointment import Appointment as AppointmentSchema, PublicBookAppointmentResponse
from app.schemas.public_information_post import PublicInformationPostPublicOut
from app.services.event_notifications import emit_in_app
from app.services.calendar_service import calendar_service
from app.services.storage_service import storage_service
from app.services.qr_service import build_appointment_qr_png_bytes, save_visitor_qr_png
from app.services.visitor_image_upload import save_visitor_base64_image

router = APIRouter()


@router.get("/info-posts", response_model=List[PublicInformationPostPublicOut])
async def list_public_info_posts(db: Session = Depends(get_db)):
    rows = (
        db.query(PublicInformationPost)
        .options(joinedload(PublicInformationPost.created_by))
        .filter(PublicInformationPost.published.is_(True))
        .order_by(
            PublicInformationPost.sort_order.asc(),
            PublicInformationPost.updated_at.desc(),
        )
        .all()
    )
    return [
        PublicInformationPostPublicOut(
            id=r.id,
            title=r.title,
            body=r.body,
            sort_order=r.sort_order,
            created_at=r.created_at,
            updated_at=r.updated_at,
            author_username=r.created_by.username if r.created_by else None,
        )
        for r in rows
    ]


class PublicAppointmentRequest(BaseModel):
    organizer_email: RelaxedEmailStr
    title: str
    description: Optional[str] = None
    preferred_date: datetime
    preferred_time: str  # Format: "HH:MM"
    visitor_name: str
    visitor_email: RelaxedEmailStr
    visitor_phone: Optional[str] = None
    visitor_company: Optional[str] = None
    # data URL ou base64 — photo du visiteur (optionnel)
    visitor_photo_base64: Optional[str] = None
    # data URL ou base64 — copie pièce d'identité (image), optionnel
    visitor_id_document_base64: Optional[str] = None


@router.post("/book-appointment", response_model=PublicBookAppointmentResponse)
async def book_appointment(
    request: PublicAppointmentRequest,
    db: Session = Depends(get_db)
):
    """Public endpoint for booking appointments"""
    organizer = (
        db.query(User)
        .options(joinedload(User.roles))
        .join(User.roles)
        .filter(
            User.email == request.organizer_email,
            Role.name.in_(["director", "master", "analyst"]),
        )
        .first()
    )
    
    if not organizer:
        raise HTTPException(
            status_code=404,
            detail="Organizer not found or not available for public bookings"
        )
    
    # Parse preferred date and time
    start_time = request.preferred_date.replace(
        hour=int(request.preferred_time.split(":")[0]),
        minute=int(request.preferred_time.split(":")[1])
    )
    end_time = start_time.replace(hour=start_time.hour + 1)  # Default 1 hour duration
    
    # Check for conflicts
    conflicts = calendar_service.check_conflicts(
        db,
        organizer.id,
        start_time,
        end_time
    )
    
    if conflicts:
        raise HTTPException(
            status_code=400,
            detail="Selected time slot is not available. Please choose another time."
        )
    
    # Create appointment (pending status - needs confirmation)
    appointment = Appointment(
        title=request.title,
        description=request.description,
        start_time=start_time,
        end_time=end_time,
        organizer_id=organizer.id,
        visitor_name=request.visitor_name,
        visitor_email=request.visitor_email,
        visitor_phone=request.visitor_phone,
        visitor_company=request.visitor_company,
        status=AppointmentStatus.PENDING,  # Requires confirmation
        booking_source=BookingSource.PUBLIC.value,
    )
    
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    
    # Create visitor record
    visitor = Visitor(
        appointment_id=appointment.id,
        name=request.visitor_name,
        email=request.visitor_email,
        phone=request.visitor_phone,
        company=request.visitor_company
    )
    
    db.add(visitor)
    db.commit()
    db.refresh(visitor)

    visitor.qr_code_path = await save_visitor_qr_png(appointment.id, visitor.id)

    rel_photo = await save_visitor_base64_image(
        request.visitor_photo_base64,
        visitor.id,
        "visitor_photos",
        error_label="Visitor photo",
    )
    if rel_photo:
        visitor.visitor_photo_path = rel_photo

    rel_doc = await save_visitor_base64_image(
        request.visitor_id_document_base64,
        visitor.id,
        "id-card",
        error_label="ID document",
    )
    if rel_doc:
        visitor.visitor_id_document_path = rel_doc
    db.add(visitor)
    db.commit()
    db.refresh(visitor)

    emit_in_app(
        db,
        [organizer.id],
        "Public booking request",
        f"{request.visitor_name} requested «{request.title}».",
        {"type": "public_booking", "appointment_id": str(appointment.id)},
    )

    row = (
        db.query(Appointment)
        .options(joinedload(Appointment.organizer), joinedload(Appointment.visitor))
        .filter(Appointment.id == appointment.id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=500, detail="Booking persist failed")

    qr_png: Optional[bytes] = None
    if row.visitor and row.visitor.qr_code_path:
        try:
            qr_png = await storage_service.get_file(row.visitor.qr_code_path)
        except Exception:
            qr_png = None
    if qr_png is None:
        qr_png = build_appointment_qr_png_bytes(row.id)

    base = AppointmentSchema.model_validate(row)
    return PublicBookAppointmentResponse(
        **base.model_dump(),
        visitor_qr_png_base64=base64.b64encode(qr_png).decode("ascii"),
    )


@router.get("/appointments/{appointment_id}/visitor-qrcode")
async def get_public_visitor_qrcode(
    appointment_id: uuid.UUID,
    download: bool = Query(False, description="Forcer Content-Disposition: attachment pour téléchargement"),
    db: Session = Depends(get_db),
):
    """Image PNG du QR visiteur (fichier storage ou régénération), sans authentification — l’UUID du RDV sert de secret faible."""
    apt = (
        db.query(Appointment)
        .options(joinedload(Appointment.visitor))
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not apt or not apt.visitor:
        raise HTTPException(status_code=404, detail="QR code not found")
    content: Optional[bytes] = None
    if apt.visitor.qr_code_path:
        try:
            content = await storage_service.get_file(apt.visitor.qr_code_path)
        except FileNotFoundError:
            content = None
        except Exception:
            content = None
    if not content:
        try:
            content = build_appointment_qr_png_bytes(apt.id)
        except Exception:
            raise HTTPException(status_code=404, detail="QR code not available")
    headers: dict[str, str] = {
        "Cache-Control": "public, max-age=300",
        "Access-Control-Allow-Origin": "*",
        "Cross-Origin-Resource-Policy": "cross-origin",
    }
    if download:
        headers["Content-Disposition"] = (
            f'attachment; filename="rendez-vous-{appointment_id}.png"'
        )
    return Response(content=content, media_type="image/png", headers=headers)


@router.get("/available-slots/{organizer_email}")
async def get_public_available_slots(
    organizer_email: str,
    date: datetime,
    duration_minutes: int = 60,
    db: Session = Depends(get_db)
):
    """Get available time slots for public booking"""
    organizer = (
        db.query(User)
        .options(joinedload(User.roles))
        .join(User.roles)
        .filter(
            User.email == organizer_email,
            Role.name.in_(["director", "master", "analyst"]),
        )
        .first()
    )
    
    if not organizer:
        raise HTTPException(
            status_code=404,
            detail="Organizer not found or not available for public bookings"
        )
    
    slots = calendar_service.get_available_slots(
        db,
        organizer.id,
        date,
        duration_minutes
    )
    
    return {
        "organizer": organizer.full_name,
        "date": date.date().isoformat(),
        "slots": [{"start": s["start"].isoformat(), "end": s["end"].isoformat()} for s in slots]
    }

