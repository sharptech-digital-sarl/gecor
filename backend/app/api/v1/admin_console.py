from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.effective_permissions import user_has_permission
from app.core.security import get_current_user
from app.models.audit_event import AuditEvent
from app.models.in_app_notification import InAppNotification
from app.models.notification import Notification
from app.models.public_information_post import PublicInformationPost
from app.models.user import User
from app.schemas.in_app_notification import InAppNotificationOut
from app.schemas.public_information_post import (
    PublicInformationPostCreate,
    PublicInformationPostOut,
    PublicInformationPostUpdate,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


def _require_master_audit(user: User) -> None:
    if not user_has_permission(user, "admin.audit"):
        raise HTTPException(status_code=403, detail="Not enough permissions")


def _require_master_notifications(user: User) -> None:
    if not user_has_permission(user, "admin.notifications"):
        raise HTTPException(status_code=403, detail="Not enough permissions")


def _require_public_posts(user: User) -> None:
    if not user_has_permission(user, "content.public_posts"):
        raise HTTPException(status_code=403, detail="Not enough permissions")


class AuditFilterOptionsOut(BaseModel):
    actions: List[str]
    resource_types: List[str]


class AdminAuditEventOut(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    actor_user_id: Optional[uuid.UUID] = None
    actor_username: Optional[str] = None
    actor_email: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[uuid.UUID] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


@router.get("/audit-logs/filter-options", response_model=AuditFilterOptionsOut)
async def audit_filter_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_master_audit(current_user)
    actions = [
        r[0]
        for r in db.query(AuditEvent.action).distinct().order_by(AuditEvent.action.asc()).all()
        if r[0]
    ]
    resource_types = [
        r[0]
        for r in db.query(AuditEvent.resource_type).distinct().order_by(AuditEvent.resource_type.asc()).all()
        if r[0]
    ]
    return AuditFilterOptionsOut(actions=actions, resource_types=resource_types)


@router.get("/audit-logs", response_model=List[AdminAuditEventOut])
async def list_audit_logs(
    from_ts: Optional[datetime] = Query(None, alias="from"),
    to_ts: Optional[datetime] = Query(None, alias="to"),
    actor_user_id: Optional[uuid.UUID] = None,
    action: Optional[List[str]] = Query(None),
    resource_type: Optional[List[str]] = Query(None),
    search: Optional[str] = Query(
        None,
        description="Recherche dans action, type, id ressource, détails (JSON)",
    ),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_master_audit(current_user)
    stmt = db.query(AuditEvent).options(joinedload(AuditEvent.actor))
    if from_ts:
        stmt = stmt.filter(AuditEvent.timestamp >= from_ts)
    if to_ts:
        stmt = stmt.filter(AuditEvent.timestamp <= to_ts)
    if actor_user_id:
        stmt = stmt.filter(AuditEvent.actor_user_id == actor_user_id)
    if action:
        stmt = stmt.filter(AuditEvent.action.in_(action))
    if resource_type:
        stmt = stmt.filter(AuditEvent.resource_type.in_(resource_type))
    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.filter(
            or_(
                AuditEvent.action.ilike(term),
                AuditEvent.resource_type.ilike(term),
                cast(AuditEvent.resource_id, String).ilike(term),
                cast(AuditEvent.details, String).ilike(term),
            )
        )
    rows = stmt.order_by(AuditEvent.timestamp.desc()).offset(offset).limit(limit).all()
    return [
        AdminAuditEventOut(
            id=r.id,
            timestamp=r.timestamp,
            actor_user_id=r.actor_user_id,
            actor_username=r.actor.username if r.actor else None,
            actor_email=r.actor.email if r.actor else None,
            action=r.action,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            details=r.details,
            ip_address=r.ip_address,
            user_agent=r.user_agent,
        )
        for r in rows
    ]


class AdminNotificationEmailItem(BaseModel):
    id: uuid.UUID
    notification_type: str
    status: str
    subject: Optional[str] = None
    message: str
    recipient_email: Optional[str] = None
    recipient_id: Optional[uuid.UUID] = None
    related_document_id: Optional[uuid.UUID] = None
    related_appointment_id: Optional[uuid.UUID] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    recipient_username: Optional[str] = None

    model_config = {"from_attributes": True}


class AdminInAppNotificationOut(InAppNotificationOut):
    user_username: Optional[str] = None
    user_email: Optional[str] = None


class AdminNotificationsOverview(BaseModel):
    in_app: List[AdminInAppNotificationOut]
    email_notifications: List[AdminNotificationEmailItem]


@router.get("/notifications", response_model=AdminNotificationsOverview)
async def admin_notifications_overview(
    in_app_limit: int = Query(200, le=500),
    email_limit: int = Query(200, le=500),
    user_id: Optional[uuid.UUID] = Query(
        None, description="Filter in-app notifications by user"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_master_notifications(current_user)
    iq = db.query(InAppNotification).options(joinedload(InAppNotification.user))
    if user_id:
        iq = iq.filter(InAppNotification.user_id == user_id)
    in_app_rows = (
        iq.order_by(InAppNotification.created_at.desc()).limit(in_app_limit).all()
    )
    email_rows = (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .limit(email_limit)
        .all()
    )
    in_app_out: List[AdminInAppNotificationOut] = []
    for n in in_app_rows:
        in_app_out.append(
            AdminInAppNotificationOut(
                id=n.id,
                user_id=n.user_id,
                title=n.title,
                body=n.body,
                payload=n.payload,
                read_at=n.read_at,
                created_at=n.created_at,
                user_username=n.user.username if n.user else None,
                user_email=n.user.email if n.user else None,
            )
        )

    email_out: List[AdminNotificationEmailItem] = []
    for n in email_rows:
        email_out.append(
            AdminNotificationEmailItem(
                id=n.id,
                notification_type=n.notification_type.value
                if hasattr(n.notification_type, "value")
                else str(n.notification_type),
                status=n.status.value if hasattr(n.status, "value") else str(n.status),
                subject=n.subject,
                message=n.message,
                recipient_email=n.recipient_email,
                recipient_id=n.recipient_id,
                recipient_username=n.recipient.username if n.recipient else None,
                related_document_id=n.related_document_id,
                related_appointment_id=n.related_appointment_id,
                sent_at=n.sent_at,
                created_at=n.created_at,
            )
        )
    return AdminNotificationsOverview(
        in_app=in_app_out,
        email_notifications=email_out,
    )


@router.get("/info-posts", response_model=List[PublicInformationPostOut])
async def admin_list_info_posts(
    include_unpublished: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_public_posts(current_user)
    q = db.query(PublicInformationPost).order_by(
        PublicInformationPost.sort_order.asc(),
        PublicInformationPost.updated_at.desc(),
    )
    if not include_unpublished:
        q = q.filter(PublicInformationPost.published.is_(True))
    return q.all()


@router.post("/info-posts", response_model=PublicInformationPostOut)
async def admin_create_info_post(
    body: PublicInformationPostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_public_posts(current_user)
    post = PublicInformationPost(
        title=body.title,
        body=body.body,
        sort_order=body.sort_order,
        published=body.published,
        created_by_id=current_user.id,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.put("/info-posts/{post_id}", response_model=PublicInformationPostOut)
async def admin_update_info_post(
    post_id: uuid.UUID,
    body: PublicInformationPostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_public_posts(current_user)
    post = db.query(PublicInformationPost).filter(PublicInformationPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(post, k, v)
    post.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(post)
    return post


@router.delete("/info-posts/{post_id}")
async def admin_delete_info_post(
    post_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_public_posts(current_user)
    post = db.query(PublicInformationPost).filter(PublicInformationPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    db.delete(post)
    db.commit()
    return {"ok": True}
