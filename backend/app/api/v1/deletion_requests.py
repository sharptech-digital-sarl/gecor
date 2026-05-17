from datetime import datetime
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.effective_permissions import user_has_permission
from app.models.deletion_request import (
    DeletionRequest,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    TARGET_APPOINTMENT,
    TARGET_MAIL,
)
from app.models.user import User, UserRole
from app.schemas.deletion_request import DeletionRequestOut, DeletionResolveBody
from app.core.security import get_current_user, require_role
from app.models.appointment import AppointmentStatus
from app.services.mail_purge_service import purge_mail_document
from app.services.appointment_cancellation_service import (
    cancel_appointment_and_external_calendars,
    load_appointment_for_cancellation,
)

router = APIRouter()


def _can_review(user: User) -> bool:
    """Master : toujours. Director / admin : trancher les demandes (équivalent métier). Autres rôles : permission explicite."""
    if user.has_role("master"):
        return True
    if user.has_any_role("director", "admin"):
        return True
    return user_has_permission(user, "deletion_requests.review")


@router.get("/", response_model=List[DeletionRequestOut])
async def list_deletion_requests(
    status: Optional[str] = Query(
        default=STATUS_PENDING,
        description="pending | approved | rejected, or 'all' for no filter",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _can_review(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    q = db.query(DeletionRequest)
    if status and status != "all":
        q = q.filter(DeletionRequest.status == status)
    return q.order_by(DeletionRequest.created_at.desc()).limit(200).all()


@router.post("/{request_id}/approve", response_model=DeletionRequestOut)
async def approve_deletion_request(
    request_id: uuid.UUID,
    body: DeletionResolveBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER, UserRole.DIRECTOR, "admin")),
):
    if not _can_review(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    req = db.query(DeletionRequest).filter(DeletionRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Deletion request not found")
    if req.status != STATUS_PENDING:
        raise HTTPException(status_code=400, detail="Request is not pending")

    if req.target_type == TARGET_MAIL:
        ok = purge_mail_document(db, req.target_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Mail document not found")
    elif req.target_type == TARGET_APPOINTMENT:
        apt = load_appointment_for_cancellation(db, req.target_id)
        if not apt:
            raise HTTPException(status_code=404, detail="Appointment not found")
        if apt.status == AppointmentStatus.CANCELLED:
            pass
        elif apt.status in (AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW):
            raise HTTPException(
                status_code=400,
                detail="Appointment cannot be cancelled in current state",
            )
        else:
            try:
                await cancel_appointment_and_external_calendars(db, apt)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        raise HTTPException(status_code=400, detail="Unknown target type")

    req.status = STATUS_APPROVED
    req.resolved_by = current_user.id
    req.resolved_at = datetime.utcnow()
    req.resolution_notes = body.resolution_notes
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.post("/{request_id}/reject", response_model=DeletionRequestOut)
async def reject_deletion_request(
    request_id: uuid.UUID,
    body: DeletionResolveBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER, UserRole.DIRECTOR, "admin")),
):
    if not _can_review(current_user):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    req = db.query(DeletionRequest).filter(DeletionRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Deletion request not found")
    if req.status != STATUS_PENDING:
        raise HTTPException(status_code=400, detail="Request is not pending")

    req.status = STATUS_REJECTED
    req.resolved_by = current_user.id
    req.resolved_at = datetime.utcnow()
    req.resolution_notes = body.resolution_notes
    db.add(req)
    db.commit()
    db.refresh(req)
    return req
