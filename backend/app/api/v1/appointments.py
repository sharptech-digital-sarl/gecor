from typing import List, Literal, Optional, Tuple
import mimetypes
import math

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, or_, exists
from datetime import datetime, timedelta
import uuid
from pydantic import BaseModel

from app.core.database import get_db
from app.core.effective_permissions import user_has_any_permission, user_has_permission
from app.core.security import get_current_user, require_role
from app.models.deletion_request import DeletionRequest, STATUS_PENDING, TARGET_APPOINTMENT
from app.models.user import User, UserRole
from app.core.audit import audit_logger
from app.core.request_ip import get_client_ip
from app.models.appointment import Appointment, AppointmentStatus, Visitor
from app.models.appointment_task import (
    AppointmentAgendaItem,
    AppointmentTask,
    AppointmentTaskStatus,
)
from app.schemas.appointment import (
    AgendaItemCreate,
    AgendaItemUpdate,
    Appointment as AppointmentSchema,
    AppointmentCreate,
    AppointmentMinutesBody,
    AppointmentTaskCreate,
    AppointmentTaskUpdate,
    AppointmentUpdate,
    CheckInResponse,
    ProposeSlotBody,
    HierarchyRejectBody,
    ReceptionFinalizeBody,
    Visitor as VisitorSchema,
)
from app.schemas.user import BulkDeleteIds, UserSummary
from app.schemas.deletion_request import DeletionRequestCreateBody
from app.services.storage_service import storage_service
from app.services.calendar_service import calendar_service
from app.services.outlook_service import outlook_service
from app.services.google_calendar_service import google_calendar_service
from app.services.event_notifications import emit_in_app, user_ids_for_deletion_reviewers
from app.services.appointment_cancellation_service import (
    cancel_appointment_and_external_calendars,
    load_appointment_for_cancellation,
)
from app.services.appointment_archive_service import (
    archive_appointment_and_external_calendars,
    load_appointment_for_archive,
)
from app.services.appointment_purge_service import (
    load_appointment_for_purge,
    permanently_delete_appointment,
)
from app.services.qr_service import (
    parse_qr_payload_to_appointment_id,
    save_visitor_qr_png,
)
from app.services.visitor_image_upload import save_visitor_base64_image
from app.core.list_highlights import appointment_highlight_destined

router = APIRouter()


def _client_meta(request: Request) -> Tuple[Optional[str], Optional[str]]:
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")
    return ip, ua


class CheckInByQrRequest(BaseModel):
    raw: str


def _appointment_broad_access(user: User) -> bool:
    """Vue liste sur tout le service : master, direction, secrétariat, accueil uniquement."""
    return user.has_any_role("master", "director", "receptionist", "secretary")


def _can_access_appointment(user: User, appointment: Appointment) -> bool:
    if _appointment_broad_access(user):
        return True
    return appointment.organizer_id == user.id


def _pending_appointment_deletion_ids(db: Session) -> set:
    rows = (
        db.query(DeletionRequest.target_id)
        .filter(
            DeletionRequest.target_type == TARGET_APPOINTMENT,
            DeletionRequest.status == STATUS_PENDING,
        )
        .all()
    )
    return {r[0] for r in rows}


def _appointment_load_options():
    return (
        joinedload(Appointment.organizer),
        joinedload(Appointment.visitor),
        joinedload(Appointment.agenda_items),
        joinedload(Appointment.followup_tasks),
    )


def _appointment_with_pending_flag(apt, pending_ids: set, current_user: User) -> AppointmentSchema:
    d = AppointmentSchema.model_validate(apt)
    return d.model_copy(
        update={
            "has_pending_deletion_request": apt.id in pending_ids,
            "highlight_destined": appointment_highlight_destined(apt, current_user.id),
        }
    )


def _appointment_search_pattern(raw: Optional[str]) -> Optional[str]:
    """Motif ILIKE sûr (supprime caractères spéciaux du LIKE)."""
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    for ch in ("%", "_", "\\"):
        s = s.replace(ch, " ")
    s = " ".join(s.split())
    if not s:
        return None
    return f"%{s}%"


def _is_host(user: User, appointment: Appointment) -> bool:
    return appointment.organizer_id == user.id


def _can_confirm_appointment(user: User, appointment: Appointment) -> bool:
    """La personne sollicitée (organisateur) ou le compte master peut confirmer."""
    if _is_host(user, appointment):
        return True
    if user.has_any_role("master"):
        return True
    return False


def _can_complete_appointment(user: User, appointment: Appointment) -> bool:
    """Personne sollicitée, master, ou rôle avec annulation directe sur ce RDV."""
    if not _can_access_appointment(user, appointment):
        return False
    if _is_host(user, appointment):
        return True
    if user.has_any_role("master"):
        return True
    if user_has_permission(user, "appointments.delete"):
        return True
    return False


def _can_cancel_appointment(user: User, appointment: Appointment) -> bool:
    """Annulation : droit delete, ou personne sollicitée pour son propre RDV."""
    if not _can_access_appointment(user, appointment):
        return False
    if user_has_permission(user, "appointments.delete"):
        return True
    if _is_host(user, appointment):
        return True
    return False


def _raise_if_archived(appointment: Appointment) -> None:
    if appointment.archived_at is not None:
        raise HTTPException(status_code=400, detail="Appointment is archived")


def _can_bulk_ops_admin(user: User) -> bool:
    return user.has_any_role("master", "director", "admin")


def _is_master_or_director(user: User) -> bool:
    return user.has_any_role("master", "director")


def _can_archive_appointment(user: User, appointment: Appointment) -> bool:
    if not _can_access_appointment(user, appointment):
        return False
    return _can_bulk_ops_admin(user)


async def _sync_appointment_to_outlook_if_configured(db: Session, appointment: Appointment) -> None:
    if not (outlook_service.use_graph_api or outlook_service.use_ews):
        return
    event_id = await outlook_service.sync_appointment_to_outlook(appointment)
    if event_id:
        appointment.outlook_event_id = event_id
        appointment.synced_with_outlook = True
        appointment.last_sync_at = datetime.utcnow()
        db.commit()
        db.refresh(appointment)


async def _sync_appointment_to_google_if_connected(db: Session, appointment: Appointment) -> None:
    if not google_calendar_service.is_configured():
        return
    organizer = appointment.organizer
    if not organizer:
        organizer = db.query(User).filter(User.id == appointment.organizer_id).first()
    if not organizer or not organizer.google_refresh_token:
        return
    event_id = await google_calendar_service.sync_appointment_to_google(
        appointment=appointment,
        organizer=organizer,
        existing_event_id=appointment.google_event_id,
    )
    if event_id:
        appointment.google_event_id = event_id
        appointment.last_sync_at = datetime.utcnow()
        db.commit()
        db.refresh(appointment)


def _compute_check_in_punctuality(
    start_time: datetime, checkin_at: datetime
) -> Tuple[Literal["early", "on_time", "late"], int]:
    """Même règle que le frontend : retard après l'heure prévue ; à l'heure dans les 5 min avant."""
    if checkin_at > start_time:
        minutes = max(1, math.ceil((checkin_at - start_time).total_seconds() / 60))
        return "late", minutes
    window_start = start_time - timedelta(minutes=5)
    if checkin_at >= window_start:
        return "on_time", 0
    minutes = max(1, math.ceil((start_time - checkin_at).total_seconds() / 60))
    return "early", minutes


def _check_in_visitor_by_appointment_id(db: Session, appointment_id: uuid.UUID) -> CheckInResponse:
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _raise_if_archived(appointment)

    visitor = db.query(Visitor).filter(Visitor.appointment_id == appointment_id).first()
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor record not found")

    if visitor.checked_in:
        raise HTTPException(status_code=400, detail="Visitor already checked in")

    visitor.checked_in = True
    visitor.checked_in_at = datetime.utcnow()
    db.commit()
    db.refresh(visitor)

    status, minutes_delta = _compute_check_in_punctuality(
        appointment.start_time, visitor.checked_in_at
    )
    emit_in_app(
        db,
        [appointment.organizer_id],
        "Visitor checked in",
        f"{appointment.visitor_name} checked in for «{appointment.title}».",
        {"type": "check_in", "appointment_id": str(appointment_id)},
    )
    return CheckInResponse(
        message="Visitor checked in successfully",
        punctuality_status=status,
        minutes_delta=minutes_delta,
    )


@router.post("/", response_model=AppointmentSchema)
async def create_appointment(
    request: Request,
    appointment_data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new appointment"""
    if not user_has_permission(current_user, "appointments.create"):
        raise HTTPException(status_code=403, detail="Not enough permissions to create appointments")
    # Check for conflicts
    conflicts = calendar_service.check_conflicts(
        db,
        appointment_data.organizer_id,
        appointment_data.start_time,
        appointment_data.end_time
    )
    
    if conflicts:
        raise HTTPException(
            status_code=400,
            detail="Appointment conflicts with existing appointment"
        )
    
    # Personne sollicitée (organizer) : doit exister et ne pas être un compte master
    organizer = (
        db.query(User)
        .options(joinedload(User.roles))
        .filter(User.id == appointment_data.organizer_id)
        .first()
    )
    if not organizer:
        raise HTTPException(status_code=404, detail="Organizer not found")
    if not organizer.is_active:
        raise HTTPException(status_code=400, detail="Selected host account is inactive")
    if organizer.has_role("master"):
        raise HTTPException(
            status_code=400,
            detail="Visit host cannot be a master account",
        )
    
    # Create appointment
    appointment = Appointment(
        title=appointment_data.title,
        description=appointment_data.description,
        start_time=appointment_data.start_time,
        end_time=appointment_data.end_time,
        location=appointment_data.location,
        organizer_id=appointment_data.organizer_id,
        visitor_name=appointment_data.visitor_name,
        visitor_email=appointment_data.visitor_email,
        visitor_phone=appointment_data.visitor_phone,
        visitor_company=appointment_data.visitor_company,
        status=AppointmentStatus.PENDING,
    )
    
    db.add(appointment)
    db.commit()
    db.refresh(appointment)
    
    # Create visitor record
    visitor = Visitor(
        appointment_id=appointment.id,
        name=appointment_data.visitor_name,
        email=appointment_data.visitor_email,
        phone=appointment_data.visitor_phone,
        company=appointment_data.visitor_company
    )
    
    db.add(visitor)
    db.commit()
    db.refresh(visitor)

    visitor.qr_code_path = await save_visitor_qr_png(appointment.id, visitor.id)

    rel_photo = await save_visitor_base64_image(
        appointment_data.visitor_photo_base64,
        visitor.id,
        "visitor_photos",
        error_label="Visitor photo",
    )
    rel_id_doc = await save_visitor_base64_image(
        appointment_data.visitor_id_document_base64,
        visitor.id,
        "id-card",
        error_label="ID document",
    )
    if rel_photo:
        visitor.visitor_photo_path = rel_photo
    if rel_id_doc:
        visitor.visitor_id_document_path = rel_id_doc
    db.add(visitor)
    db.commit()
    db.refresh(visitor)
    
    # Refresh appointment to load relationships
    db.refresh(appointment)
    
    # Eager load relationships
    appointment = (
        db.query(Appointment)
        .options(*_appointment_load_options())
        .filter(Appointment.id == appointment.id)
        .first()
    )

    # Outlook : synchronisation après confirmation par la personne sollicitée (voir /confirm)

    ip, ua = _client_meta(request)
    audit_logger.log_appointment_change(
        current_user.id,
        appointment.id,
        "appointment_create",
        changes={"title": appointment.title},
        ip_address=ip,
        user_agent=ua,
    )
    emit_in_app(
        db,
        [appointment.organizer_id],
        "New appointment",
        f"{appointment.visitor_name} — {appointment.title}",
        {"type": "appointment", "appointment_id": str(appointment.id)},
    )

    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.get("/", response_model=List[AppointmentSchema])
async def list_appointments(
    skip: int = 0,
    limit: int = 100,
    organizer_id: Optional[uuid.UUID] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[AppointmentStatus] = None,
    include_archived: bool = False,
    search: Optional[str] = None,
    booking_source: Optional[str] = None,
    checked_in: Optional[bool] = None,
    reception_validated: Optional[bool] = None,
    pending_cancellation_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List appointments"""
    query = db.query(Appointment)

    if include_archived:
        if not (
            _can_bulk_ops_admin(current_user)
            and user_has_permission(current_user, "appointments.delete")
        ):
            raise HTTPException(
                status_code=403,
                detail="Not enough permissions to include archived appointments",
            )
    else:
        query = query.filter(Appointment.archived_at.is_(None))
    
    if organizer_id:
        query = query.filter(Appointment.organizer_id == organizer_id)
    elif not _appointment_broad_access(current_user):
        query = query.filter(Appointment.organizer_id == current_user.id)
    
    if start_date:
        query = query.filter(Appointment.start_time >= start_date)
    if end_date:
        query = query.filter(Appointment.start_time <= end_date)
    if status:
        query = query.filter(Appointment.status == status)

    pat = _appointment_search_pattern(search)
    if pat:
        query = query.filter(
            or_(
                Appointment.title.ilike(pat),
                Appointment.description.ilike(pat),
                Appointment.visitor_name.ilike(pat),
                Appointment.visitor_email.ilike(pat),
                Appointment.visitor_phone.ilike(pat),
                Appointment.visitor_company.ilike(pat),
                Appointment.location.ilike(pat),
            )
        )

    if booking_source:
        bs = booking_source.strip().lower()
        if bs in ("internal", "public"):
            query = query.filter(Appointment.booking_source == bs)

    if checked_in is not None:
        if checked_in:
            query = query.join(Visitor).filter(Visitor.checked_in.is_(True))
        else:
            query = query.outerjoin(Visitor).filter(
                or_(Visitor.id.is_(None), Visitor.checked_in.is_(False))
            )

    if reception_validated is not None:
        if reception_validated:
            query = query.filter(Appointment.reception_validated_at.isnot(None))
        else:
            query = query.filter(Appointment.reception_validated_at.is_(None))

    if pending_cancellation_only:
        query = query.filter(
            exists().where(
                (DeletionRequest.target_id == Appointment.id)
                & (DeletionRequest.target_type == TARGET_APPOINTMENT)
                & (DeletionRequest.status == STATUS_PENDING)
            )
        )
    
    appointments = (
        query.options(*_appointment_load_options())
        .order_by(Appointment.start_time)
        .offset(skip)
        .limit(limit)
        .all()
    )
    pending = _pending_appointment_deletion_ids(db)
    return [_appointment_with_pending_flag(a, pending, current_user) for a in appointments]


@router.post("/bulk-delete")
async def bulk_delete_appointments(
    body: BulkDeleteIds,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Annule plusieurs rendez-vous (master, director ou rôle admin)."""
    if not current_user.has_any_role("master", "director", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Only master and director can bulk-delete appointments",
        )
    deleted: List[str] = []
    skipped: List[dict] = []
    for aid in body.ids:
        appointment = load_appointment_for_cancellation(db, aid)
        if not appointment:
            skipped.append({"id": str(aid), "reason": "not_found"})
            continue
        if appointment.archived_at is not None:
            skipped.append({"id": str(aid), "reason": "archived"})
            continue
        if not _can_cancel_appointment(current_user, appointment):
            skipped.append({"id": str(aid), "reason": "forbidden"})
            continue
        if appointment.status in (
            AppointmentStatus.CANCELLED,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.NO_SHOW,
        ):
            skipped.append({"id": str(aid), "reason": "already_final"})
            continue
        try:
            await cancel_appointment_and_external_calendars(db, appointment)
        except ValueError as exc:
            skipped.append({"id": str(aid), "reason": str(exc)})
            continue
        deleted.append(str(aid))
    db.commit()
    return {"deleted": deleted, "skipped": skipped, "deleted_count": len(deleted)}


@router.post("/bulk-archive")
async def bulk_archive_appointments(
    body: BulkDeleteIds,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Archive plusieurs rendez-vous (master, director ou admin)."""
    if not _can_bulk_ops_admin(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only master, director and admin can archive appointments",
        )
    if not user_has_permission(current_user, "appointments.delete"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    archived_ids: List[str] = []
    skipped: List[dict] = []
    for aid in body.ids:
        appointment = load_appointment_for_archive(db, aid)
        if not appointment:
            skipped.append({"id": str(aid), "reason": "not_found"})
            continue
        if appointment.archived_at is not None:
            skipped.append({"id": str(aid), "reason": "already_archived"})
            continue
        if not _can_archive_appointment(current_user, appointment):
            skipped.append({"id": str(aid), "reason": "forbidden"})
            continue
        await archive_appointment_and_external_calendars(db, appointment)
        archived_ids.append(str(aid))
    db.commit()
    return {
        "archived": archived_ids,
        "skipped": skipped,
        "archived_count": len(archived_ids),
    }


@router.post("/bulk-permanent-delete")
async def bulk_permanent_delete_appointments(
    body: BulkDeleteIds,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Supprime définitivement des rendez-vous (master ou director uniquement)."""
    if not _is_master_or_director(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only master and director can permanently delete appointments",
        )
    if not user_has_permission(current_user, "appointments.delete"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    deleted: List[str] = []
    skipped: List[dict] = []
    for aid in body.ids:
        appointment = load_appointment_for_purge(db, aid)
        if not appointment:
            skipped.append({"id": str(aid), "reason": "not_found"})
            continue
        if not _can_access_appointment(current_user, appointment):
            skipped.append({"id": str(aid), "reason": "forbidden"})
            continue
        try:
            await permanently_delete_appointment(db, appointment)
        except Exception as exc:
            skipped.append({"id": str(aid), "reason": str(exc)})
            continue
        deleted.append(str(aid))
    db.commit()
    return {"deleted": deleted, "skipped": skipped, "deleted_count": len(deleted)}


@router.get("/{appointment_id}/visitor/photo")
async def get_visitor_photo(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    visitor = db.query(Visitor).filter(Visitor.appointment_id == appointment_id).first()
    if not visitor or not visitor.visitor_photo_path:
        raise HTTPException(status_code=404, detail="Visitor photo not found")
    file_content = await storage_service.get_file(visitor.visitor_photo_path)
    mime_type, _ = mimetypes.guess_type(visitor.visitor_photo_path)
    if not mime_type:
        mime_type = "image/jpeg"
    return Response(
        content=file_content,
        media_type=mime_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/{appointment_id}/visitor/id-document")
async def get_visitor_id_document(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    visitor = db.query(Visitor).filter(Visitor.appointment_id == appointment_id).first()
    if not visitor or not visitor.visitor_id_document_path:
        raise HTTPException(status_code=404, detail="Visitor ID document not found")
    file_content = await storage_service.get_file(visitor.visitor_id_document_path)
    mime_type, _ = mimetypes.guess_type(visitor.visitor_id_document_path)
    if not mime_type:
        mime_type = "image/jpeg"
    return Response(
        content=file_content,
        media_type=mime_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/{appointment_id}/visitor/qrcode")
async def get_visitor_qrcode(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    visitor = db.query(Visitor).filter(Visitor.appointment_id == appointment_id).first()
    if not visitor or not visitor.qr_code_path:
        raise HTTPException(status_code=404, detail="Visitor QR code not found")
    try:
        file_content = await storage_service.get_file(visitor.qr_code_path)
    except (FileNotFoundError, OSError):
        raise HTTPException(status_code=404, detail="Visitor QR code file missing")
    except Exception:
        raise HTTPException(status_code=404, detail="Visitor QR code not available")
    return Response(
        content=file_content,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/{appointment_id}", response_model=AppointmentSchema)
async def get_appointment(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get appointment by ID"""
    appointment = (
        db.query(Appointment)
        .options(*_appointment_load_options())
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")

    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.post("/{appointment_id}/confirm", response_model=AppointmentSchema)
async def confirm_appointment(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Valide le rendez-vous en attente (personne sollicitée ou master)."""
    appointment = (
        db.query(Appointment)
        .options(*_appointment_load_options())
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)
    if not _can_confirm_appointment(current_user, appointment):
        raise HTTPException(
            status_code=403,
            detail="Only the solicited person or master can confirm this appointment",
        )
    _confirmable = (
        AppointmentStatus.PENDING,
        AppointmentStatus.SLOT_PROPOSED,
        AppointmentStatus.PREPARATION,
    )
    if appointment.status not in _confirmable:
        raise HTTPException(
            status_code=400,
            detail="This appointment cannot be confirmed from its current status",
        )

    if (
        appointment.status == AppointmentStatus.SLOT_PROPOSED
        and appointment.proposed_start_time
        and appointment.proposed_end_time
    ):
        appointment.start_time = appointment.proposed_start_time
        appointment.end_time = appointment.proposed_end_time

    appointment.status = AppointmentStatus.CONFIRMED
    db.commit()
    db.refresh(appointment)

    emit_in_app(
        db,
        [appointment.organizer_id],
        "Appointment confirmed",
        f"«{appointment.title}» is confirmed.",
        {"type": "appointment_confirm", "appointment_id": str(appointment.id)},
    )

    await _sync_appointment_to_outlook_if_configured(db, appointment)
    await _sync_appointment_to_google_if_connected(db, appointment)
    appointment = (
        db.query(Appointment)
        .options(*_appointment_load_options())
        .filter(Appointment.id == appointment_id)
        .first()
    )

    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.post("/{appointment_id}/complete", response_model=AppointmentSchema)
async def complete_appointment(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marque le rendez-vous comme ayant eu lieu (terminé)."""
    appointment = (
        db.query(Appointment)
        .options(joinedload(Appointment.organizer), joinedload(Appointment.visitor))
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_complete_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)
    if appointment.status != AppointmentStatus.CONFIRMED:
        raise HTTPException(
            status_code=400,
            detail="Only confirmed appointments can be marked as completed",
        )

    appointment.status = AppointmentStatus.COMPLETED
    db.commit()
    db.refresh(appointment)

    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.post("/{appointment_id}/no-show", response_model=AppointmentSchema)
async def mark_appointment_no_show(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Le visiteur ne s’est pas présenté (équivalent « no-show »)."""
    appointment = (
        db.query(Appointment)
        .options(joinedload(Appointment.organizer), joinedload(Appointment.visitor))
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_complete_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)
    if appointment.status != AppointmentStatus.CONFIRMED:
        raise HTTPException(
            status_code=400,
            detail="Only confirmed appointments can be marked as no-show",
        )

    appointment.status = AppointmentStatus.NO_SHOW
    db.commit()
    db.refresh(appointment)

    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.post("/{appointment_id}/cancel")
async def cancel_appointment_by_host(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Annule le rendez-vous (personne sollicitée ou droit d’annulation directe)."""
    appointment = load_appointment_for_cancellation(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_cancel_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)
    if appointment.status in (
        AppointmentStatus.CANCELLED,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.NO_SHOW,
    ):
        raise HTTPException(
            status_code=400,
            detail="Appointment is already cancelled, completed, or marked no-show",
        )

    try:
        await cancel_appointment_and_external_calendars(db, appointment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()

    return {"message": "Appointment cancelled successfully"}


@router.post("/{appointment_id}/archive", response_model=AppointmentSchema)
async def archive_appointment_endpoint(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Archive un rendez-vous (retrait des vues opérationnelles et des compteurs)."""
    if not user_has_permission(current_user, "appointments.delete"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    appointment = load_appointment_for_archive(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.archived_at is not None:
        raise HTTPException(status_code=400, detail="Appointment is already archived")
    if not _can_archive_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    await archive_appointment_and_external_calendars(db, appointment)
    db.commit()
    appointment = (
        db.query(Appointment)
        .options(*_appointment_load_options())
        .filter(Appointment.id == appointment_id)
        .first()
    )
    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.post("/{appointment_id}/deletion-request")
async def request_appointment_deletion(
    appointment_id: uuid.UUID,
    body: DeletionRequestCreateBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not user_has_permission(current_user, "appointments.request_delete"):
        raise HTTPException(status_code=403, detail="Not enough permissions to request cancellation")
    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)
    dup = (
        db.query(DeletionRequest)
        .filter(
            DeletionRequest.target_type == TARGET_APPOINTMENT,
            DeletionRequest.target_id == appointment_id,
            DeletionRequest.status == STATUS_PENDING,
        )
        .first()
    )
    if dup:
        raise HTTPException(
            status_code=400,
            detail="A cancellation request is already pending for this appointment",
        )
    req = DeletionRequest(
        target_type=TARGET_APPOINTMENT,
        target_id=appointment_id,
        reason=body.reason,
        requested_by=current_user.id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    reviewers = user_ids_for_deletion_reviewers(db)
    emit_in_app(
        db,
        reviewers,
        "Cancellation request (appointment)",
        f"«{appointment.title}» — review required.",
        {
            "type": "deletion_request",
            "target": "appointment",
            "appointment_id": str(appointment_id),
        },
    )
    return {"id": str(req.id), "message": "Cancellation request submitted"}


@router.post("/{appointment_id}/reception-finalize", response_model=AppointmentSchema)
async def reception_finalize_appointment(
    appointment_id: uuid.UUID,
    body: ReceptionFinalizeBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Réception / secrétariat : enregistrer notes, valider la fiche, optionnellement e-mail de confirmation au visiteur (tous RDV avec e-mail visiteur)."""
    appointment = (
        db.query(Appointment)
        .options(joinedload(Appointment.organizer), joinedload(Appointment.visitor))
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not user_has_permission(current_user, "appointments.update"):
        raise HTTPException(status_code=403, detail="Not enough permissions to update appointments")
    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)

    if body.internal_notes is not None:
        appointment.internal_notes = body.internal_notes

    if appointment.reception_validated_at is None:
        appointment.reception_validated_at = datetime.utcnow()
        appointment.reception_validated_by_id = current_user.id

    if body.send_visitor_email:
        if appointment.visitor_email and (
            appointment.visitor_booking_email_sent_at is None or body.force_resend_visitor_email
        ):
            from app.tasks.notification_tasks import send_public_booking_confirmation_task

            send_public_booking_confirmation_task.delay(str(appointment.id))

    db.commit()
    db.refresh(appointment)

    ip, ua = _client_meta(request)
    audit_logger.log_appointment_change(
        current_user.id,
        appointment.id,
        "reception_finalize",
        changes={"send_visitor_email": body.send_visitor_email},
        ip_address=ip,
        user_agent=ua,
    )

    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.put("/{appointment_id}", response_model=AppointmentSchema)
async def update_appointment(
    appointment_id: uuid.UUID,
    appointment_update: AppointmentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update appointment"""
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if not user_has_permission(current_user, "appointments.update"):
        raise HTTPException(status_code=403, detail="Not enough permissions to update appointments")
    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)

    update_data = appointment_update.model_dump(exclude_unset=True)
    
    # Check for conflicts if time is being changed
    if "start_time" in update_data or "end_time" in update_data:
        start_time = update_data.get("start_time", appointment.start_time)
        end_time = update_data.get("end_time", appointment.end_time)
        
        conflicts = calendar_service.check_conflicts(
            db,
            appointment.organizer_id,
            start_time,
            end_time,
            exclude_appointment_id=appointment_id
        )
        
        if conflicts:
            raise HTTPException(
                status_code=400,
                detail="Updated appointment conflicts with existing appointment"
            )
    
    for field, value in update_data.items():
        setattr(appointment, field, value)
    
    db.commit()
    db.refresh(appointment)

    ip, ua = _client_meta(request)
    audit_logger.log_appointment_change(
        current_user.id,
        appointment.id,
        "appointment_update",
        changes=update_data,
        ip_address=ip,
        user_agent=ua,
    )
    emit_in_app(
        db,
        [appointment.organizer_id],
        "Appointment updated",
        f"«{appointment.title}» was modified.",
        {"type": "appointment_update", "appointment_id": str(appointment.id)},
    )
    
    # Re-sync to Outlook if configured
    if (outlook_service.use_graph_api or outlook_service.use_ews) and appointment.outlook_event_id:
        await outlook_service.sync_appointment_to_outlook(appointment)
    if google_calendar_service.is_configured():
        await _sync_appointment_to_google_if_connected(db, appointment)

    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.delete("/{appointment_id}")
async def delete_appointment(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Annule le rendez-vous (même règles que POST /cancel)."""
    appointment = load_appointment_for_cancellation(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_cancel_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Not enough permissions to cancel appointments")
    _raise_if_archived(appointment)
    if appointment.status in (
        AppointmentStatus.CANCELLED,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.NO_SHOW,
    ):
        raise HTTPException(
            status_code=400,
            detail="Appointment is already cancelled, completed, or marked no-show",
        )

    try:
        await cancel_appointment_and_external_calendars(db, appointment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()

    return {"message": "Appointment cancelled successfully"}


@router.delete("/{appointment_id}/permanent")
async def permanent_delete_appointment_endpoint(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Suppression définitive (base + pièces liées). Réservé au master et à la direction."""
    if not _is_master_or_director(current_user):
        raise HTTPException(
            status_code=403,
            detail="Only master and director can permanently delete appointments",
        )
    if not user_has_permission(current_user, "appointments.delete"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    appointment = load_appointment_for_purge(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        await permanently_delete_appointment(db, appointment)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    db.commit()
    return {"message": "Appointment permanently deleted"}


@router.get("/available-slots/{organizer_id}")
async def get_available_slots(
    organizer_id: uuid.UUID,
    date: datetime,
    duration_minutes: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Créneaux libres pour un organisateur (coordination / vérification d'agenda)."""
    if not user_has_permission(current_user, "appointments.view"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    slots = calendar_service.get_available_slots(
        db,
        organizer_id,
        date,
        duration_minutes
    )
    
    return {"slots": slots}


@router.get("/reception/today", response_model=List[AppointmentSchema])
async def get_today_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.RECEPTIONIST, UserRole.MASTER, UserRole.DIRECTOR))
):
    """Get today's appointments for reception dashboard"""
    from sqlalchemy.orm import joinedload
    
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start.replace(hour=23, minute=59, second=59)
    
    # Query with eager loading
    appointments = db.query(Appointment).options(
        joinedload(Appointment.organizer),
        joinedload(Appointment.visitor)
    ).filter(
        Appointment.start_time >= today_start,
        Appointment.start_time <= today_end,
        Appointment.archived_at.is_(None),
    ).order_by(Appointment.start_time).all()

    pending_ids = _pending_appointment_deletion_ids(db)

    # Convert SQLAlchemy objects to Pydantic models
    # Build dictionaries explicitly to ensure all fields are present
    result = []
    for apt in appointments:
        # Query organizer explicitly and build dict with all required fields
        organizer_data = None
        if apt.organizer_id:
            # Query with explicit column selection to ensure all fields are loaded
            stmt = select(User).where(User.id == apt.organizer_id)
            organizer = db.execute(stmt).scalar_one_or_none()
            if organizer:
                # Force refresh to ensure all attributes are loaded
                db.refresh(organizer)
                # Access all fields explicitly to trigger lazy loading if needed
                # This ensures all attributes are loaded from the database
                _ = organizer.id, organizer.username, organizer.full_name, organizer.email, organizer.role
                
                # Build dict with all required fields
                org_dict = {
                    'id': organizer.id,
                    'username': organizer.username,
                    'full_name': organizer.full_name,
                    'email': organizer.email,
                    'role': organizer.role
                }
                organizer_data = UserSummary.model_validate(org_dict)
        
        # Query visitor explicitly and build dict with all required fields
        visitor_data = None
        stmt = select(Visitor).where(Visitor.appointment_id == apt.id)
        visitor = db.execute(stmt).scalar_one_or_none()
        if visitor:
            # Force refresh to ensure all attributes are loaded
            db.refresh(visitor)
            # Access all fields explicitly to trigger lazy loading if needed
            # This ensures all attributes are loaded from the database
            _ = (visitor.id, visitor.appointment_id, visitor.name, visitor.email, 
                 visitor.phone, visitor.company, visitor.id_number, visitor.qr_code_path,
                 visitor.visitor_photo_path,
                 getattr(visitor, "visitor_id_document_path", None),
                 visitor.checked_in, visitor.checked_in_at, visitor.created_at)
            
            # Build dict with all required fields
            vis_dict = {
                'id': visitor.id,
                'appointment_id': visitor.appointment_id,
                'name': visitor.name,
                'email': visitor.email,
                'phone': visitor.phone,
                'company': visitor.company,
                'id_number': visitor.id_number,
                'qr_code_path': visitor.qr_code_path,
                'visitor_photo_path': visitor.visitor_photo_path,
                'visitor_id_document_path': getattr(visitor, "visitor_id_document_path", None),
                'checked_in': visitor.checked_in,
                'checked_in_at': visitor.checked_in_at,
                'created_at': visitor.created_at
            }
            visitor_data = VisitorSchema.model_validate(vis_dict)
        
        # Build appointment dict with all fields
        # Convert Pydantic objects to dicts for nested relationships
        apt_dict = {
            'id': apt.id,
            'organizer_id': apt.organizer_id,
            'title': apt.title,
            'description': apt.description,
            'start_time': apt.start_time,
            'end_time': apt.end_time,
            'location': apt.location,
            'visitor_name': apt.visitor_name,
            'visitor_email': apt.visitor_email,
            'visitor_phone': apt.visitor_phone,
            'visitor_company': apt.visitor_company,
            'status': apt.status,
            'booking_source': getattr(apt, "booking_source", None) or "internal",
            'internal_notes': getattr(apt, "internal_notes", None),
            'reception_validated_at': getattr(apt, "reception_validated_at", None),
            'reception_validated_by_id': getattr(apt, "reception_validated_by_id", None),
            'visitor_booking_email_sent_at': getattr(apt, "visitor_booking_email_sent_at", None),
            'reminder_sent': apt.reminder_sent,
            'reminder_sent_at': apt.reminder_sent_at,
            'outlook_event_id': apt.outlook_event_id,
            'google_event_id': apt.google_event_id,
            'synced_with_outlook': apt.synced_with_outlook,
            'created_at': apt.created_at,
            'updated_at': apt.updated_at,
            'archived_at': getattr(apt, "archived_at", None),
            'proposed_start_time': getattr(apt, "proposed_start_time", None),
            'proposed_end_time': getattr(apt, "proposed_end_time", None),
            'hierarchy_validated_at': getattr(apt, "hierarchy_validated_at", None),
            'hierarchy_validated_by_id': getattr(apt, "hierarchy_validated_by_id", None),
            'minutes_text': getattr(apt, "minutes_text", None),
            'minutes_at': getattr(apt, "minutes_at", None),
            'minutes_author_id': getattr(apt, "minutes_author_id", None),
            'agenda_items': [],
            'followup_tasks': [],
            'has_pending_deletion_request': apt.id in pending_ids,
            'organizer': organizer_data.model_dump(mode='python', exclude_none=False) if organizer_data else None,
            'visitor': visitor_data.model_dump(mode='python', exclude_none=False) if visitor_data else None
        }
        
        # Use model_construct to build the schema, which handles nested dicts better
        try:
            appointment_schema = AppointmentSchema.model_validate(apt_dict)
            result.append(appointment_schema)
        except Exception as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error validating appointment {apt.id}: {str(e)}")
            logger.error(f"Organizer data: {organizer_data.model_dump() if organizer_data else None}")
            logger.error(f"Visitor data: {visitor_data.model_dump() if visitor_data else None}")
            # Re-raise to see the full error
            raise
    
    return result


@router.post("/{appointment_id}/workflow/propose-slot", response_model=AppointmentSchema)
async def appointment_propose_slot(
    appointment_id: uuid.UUID,
    body: ProposeSlotBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_has_permission(current_user, "appointments.workflow.propose_slot"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    appointment = (
        db.query(Appointment)
        .options(*_appointment_load_options())
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)
    if appointment.status != AppointmentStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending appointments accept a slot proposal")
    conflicts = calendar_service.check_conflicts(
        db,
        appointment.organizer_id,
        body.proposed_start_time,
        body.proposed_end_time,
        exclude_appointment_id=appointment_id,
    )
    if conflicts:
        raise HTTPException(status_code=400, detail="Proposed slot conflicts with an existing appointment")
    appointment.proposed_start_time = body.proposed_start_time
    appointment.proposed_end_time = body.proposed_end_time
    appointment.start_time = body.proposed_start_time
    appointment.end_time = body.proposed_end_time
    appointment.status = AppointmentStatus.SLOT_PROPOSED
    db.commit()
    db.refresh(appointment)
    ip, ua = _client_meta(request)
    audit_logger.log_appointment_change(
        current_user.id,
        appointment.id,
        "propose_slot",
        changes={"start": str(body.proposed_start_time)},
        ip_address=ip,
        user_agent=ua,
    )
    if current_user.id != appointment.organizer_id:
        emit_in_app(
            db,
            [appointment.organizer_id],
            "RDV — créneau proposé",
            f"«{appointment.title}» : un créneau a été proposé.",
            {
                "type": "appointment_slot_proposed",
                "appointment_id": str(appointment.id),
            },
        )
    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.post("/{appointment_id}/workflow/hierarchy-validate", response_model=AppointmentSchema)
async def appointment_hierarchy_validate(
    appointment_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_has_permission(current_user, "appointments.workflow.hierarchy_validate"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    appointment = (
        db.query(Appointment)
        .options(*_appointment_load_options())
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)
    if appointment.status != AppointmentStatus.SLOT_PROPOSED:
        raise HTTPException(status_code=400, detail="Only slot-proposed appointments can be hierarchy-validated")
    appointment.hierarchy_validated_at = datetime.utcnow()
    appointment.hierarchy_validated_by_id = current_user.id
    appointment.status = AppointmentStatus.PREPARATION
    db.commit()
    db.refresh(appointment)
    ip, ua = _client_meta(request)
    audit_logger.log_appointment_change(
        current_user.id,
        appointment.id,
        "hierarchy_validate",
        changes={},
        ip_address=ip,
        user_agent=ua,
    )
    if current_user.id != appointment.organizer_id:
        emit_in_app(
            db,
            [appointment.organizer_id],
            "RDV — validation hiérarchique",
            f"«{appointment.title}» est prêt pour confirmation.",
            {
                "type": "appointment_hierarchy_validated",
                "appointment_id": str(appointment.id),
            },
        )
    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.post("/{appointment_id}/workflow/hierarchy-reject", response_model=AppointmentSchema)
async def appointment_hierarchy_reject(
    appointment_id: uuid.UUID,
    body: HierarchyRejectBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Refus DG : annule le RDV lorsqu'un créneau était proposé (équivalent décision négative)."""
    if not user_has_permission(current_user, "appointments.workflow.hierarchy_validate"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    appointment = (
        db.query(Appointment)
        .options(*_appointment_load_options())
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)
    if appointment.status != AppointmentStatus.SLOT_PROPOSED:
        raise HTTPException(
            status_code=400,
            detail="Only slot-proposed appointments can be rejected by hierarchy",
        )
    try:
        await cancel_appointment_and_external_calendars(db, appointment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(appointment)
    ip, ua = _client_meta(request)
    audit_logger.log_appointment_change(
        current_user.id,
        appointment.id,
        "hierarchy_reject",
        changes={"reason": (body.reason or "").strip() or None},
        ip_address=ip,
        user_agent=ua,
    )
    if current_user.id != appointment.organizer_id:
        emit_in_app(
            db,
            [appointment.organizer_id],
            "RDV — refus hiérarchique",
            f"«{appointment.title}» a été refusé après proposition de créneau.",
            {
                "type": "appointment_hierarchy_rejected",
                "appointment_id": str(appointment.id),
            },
        )
    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.patch("/{appointment_id}/minutes", response_model=AppointmentSchema)
async def appointment_patch_minutes(
    appointment_id: uuid.UUID,
    body: AppointmentMinutesBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_has_permission(current_user, "appointments.workflow.minutes"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    appointment = (
        db.query(Appointment)
        .options(*_appointment_load_options())
        .filter(Appointment.id == appointment_id)
        .first()
    )
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)
    appointment.minutes_text = body.minutes_text
    appointment.minutes_at = datetime.utcnow()
    appointment.minutes_author_id = current_user.id
    db.commit()
    db.refresh(appointment)
    ip, ua = _client_meta(request)
    audit_logger.log_appointment_change(
        current_user.id,
        appointment.id,
        "minutes_update",
        changes={},
        ip_address=ip,
        user_agent=ua,
    )
    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.post("/{appointment_id}/agenda-items", response_model=AppointmentSchema)
async def appointment_add_agenda_item(
    appointment_id: uuid.UUID,
    body: AgendaItemCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_has_any_permission(
        current_user,
        "appointments.workflow.agenda",
        "appointments.update",
        "appointments.workflow.tasks",
    ):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)
    item = AppointmentAgendaItem(
        appointment_id=appointment_id,
        sort_order=body.sort_order,
        title=body.title,
        body=body.body,
    )
    db.add(item)
    db.commit()
    ip, ua = _client_meta(request)
    audit_logger.log_appointment_change(
        current_user.id,
        appointment.id,
        "agenda_item_add",
        changes={"title": body.title},
        ip_address=ip,
        user_agent=ua,
    )
    appointment = (
        db.query(Appointment)
        .options(*_appointment_load_options())
        .filter(Appointment.id == appointment_id)
        .first()
    )
    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.put("/agenda-items/{item_id}", response_model=AppointmentSchema)
async def appointment_update_agenda_item(
    item_id: uuid.UUID,
    body: AgendaItemUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_has_any_permission(
        current_user,
        "appointments.workflow.agenda",
        "appointments.update",
        "appointments.workflow.tasks",
    ):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    item = db.query(AppointmentAgendaItem).filter(AppointmentAgendaItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Agenda item not found")
    appointment = db.query(Appointment).filter(Appointment.id == item.appointment_id).first()
    if not appointment or not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(item, k, v)
    db.commit()
    ip, ua = _client_meta(request)
    audit_logger.log_appointment_change(
        current_user.id,
        appointment.id,
        "agenda_item_update",
        changes={"item_id": str(item_id)},
        ip_address=ip,
        user_agent=ua,
    )
    appointment = (
        db.query(Appointment)
        .options(*_appointment_load_options())
        .filter(Appointment.id == item.appointment_id)
        .first()
    )
    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.delete("/agenda-items/{item_id}", response_model=AppointmentSchema)
async def appointment_delete_agenda_item(
    item_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_has_any_permission(
        current_user,
        "appointments.workflow.agenda",
        "appointments.update",
        "appointments.workflow.tasks",
    ):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    item = db.query(AppointmentAgendaItem).filter(AppointmentAgendaItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Agenda item not found")
    appt_id = item.appointment_id
    appointment = db.query(Appointment).filter(Appointment.id == appt_id).first()
    if not appointment or not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)
    db.delete(item)
    db.commit()
    ip, ua = _client_meta(request)
    audit_logger.log_appointment_change(
        current_user.id,
        appointment.id,
        "agenda_item_delete",
        changes={"item_id": str(item_id)},
        ip_address=ip,
        user_agent=ua,
    )
    appointment = (
        db.query(Appointment)
        .options(*_appointment_load_options())
        .filter(Appointment.id == appt_id)
        .first()
    )
    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.post("/{appointment_id}/tasks", response_model=AppointmentSchema)
async def appointment_add_task(
    appointment_id: uuid.UUID,
    body: AppointmentTaskCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_has_any_permission(
        current_user, "appointments.update", "appointments.workflow.tasks"
    ):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)
    task = AppointmentTask(
        appointment_id=appointment_id,
        title=body.title,
        description=body.description,
        assignee_id=body.assignee_id,
        due_at=body.due_at,
        status=AppointmentTaskStatus.OPEN,
    )
    db.add(task)
    db.commit()
    ip, ua = _client_meta(request)
    audit_logger.log_appointment_change(
        current_user.id,
        appointment.id,
        "task_add",
        changes={"title": body.title},
        ip_address=ip,
        user_agent=ua,
    )
    appointment = (
        db.query(Appointment)
        .options(*_appointment_load_options())
        .filter(Appointment.id == appointment_id)
        .first()
    )
    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.put("/tasks/{task_id}", response_model=AppointmentSchema)
async def appointment_update_task(
    task_id: uuid.UUID,
    body: AppointmentTaskUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_has_any_permission(
        current_user, "appointments.update", "appointments.workflow.tasks"
    ):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    task = db.query(AppointmentTask).filter(AppointmentTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    appointment = db.query(Appointment).filter(Appointment.id == task.appointment_id).first()
    if not appointment or not _can_access_appointment(current_user, appointment):
        raise HTTPException(status_code=403, detail="Access denied")
    _raise_if_archived(appointment)
    data = body.model_dump(exclude_unset=True)
    st = data.pop("status", None)
    if st is not None:
        try:
            task.status = AppointmentTaskStatus(st)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid task status")
    for k, v in data.items():
        setattr(task, k, v)
    db.commit()
    ip, ua = _client_meta(request)
    audit_logger.log_appointment_change(
        current_user.id,
        appointment.id,
        "task_update",
        changes={"task_id": str(task_id)},
        ip_address=ip,
        user_agent=ua,
    )
    appointment = (
        db.query(Appointment)
        .options(*_appointment_load_options())
        .filter(Appointment.id == task.appointment_id)
        .first()
    )
    pending = _pending_appointment_deletion_ids(db)
    return _appointment_with_pending_flag(appointment, pending, current_user)


@router.post("/{appointment_id}/check-in", response_model=CheckInResponse)
async def check_in_visitor(
    appointment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check in a visitor"""
    if not user_has_permission(current_user, "reception.checkin"):
        raise HTTPException(status_code=403, detail="Not enough permissions to check in visitors")
    return _check_in_visitor_by_appointment_id(db, appointment_id)


@router.post("/check-in-by-qr", response_model=CheckInResponse)
async def check_in_visitor_by_qr(
    payload: CheckInByQrRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check in a visitor using raw QR payload"""
    if not user_has_permission(current_user, "reception.checkin"):
        raise HTTPException(status_code=403, detail="Not enough permissions to check in visitors")
    appointment_id = parse_qr_payload_to_appointment_id(payload.raw)
    return _check_in_visitor_by_appointment_id(db, appointment_id)

