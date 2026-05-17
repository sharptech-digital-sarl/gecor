import asyncio
import queue
from datetime import datetime
from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.in_app_notification import InAppNotification
from app.models.push_subscription import PushSubscription
from app.models.user import User
from app.schemas.in_app_notification import (
    InAppNotificationOut,
    PushSubscriptionBody,
    VapidPublicOut,
)
from app.services.notification_sse_hub import notification_sse_hub

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/stream")
async def notification_events_stream(current_user: User = Depends(get_current_user)):
    """
    Flux SSE : événements lorsque l’utilisateur reçoit une notification in-app (processus API).
    Authentification : en-tête Authorization Bearer (utiliser fetch côté SPA, pas EventSource natif).
    """
    hub = notification_sse_hub
    q = hub.subscribe(current_user.id)

    async def gen():
        try:
            yield ": connected\n\n"
            while True:

                def _wait() -> str | None:
                    try:
                        return q.get(timeout=25)
                    except queue.Empty:
                        return None

                item = await asyncio.to_thread(_wait)
                if item is None:
                    yield ": ping\n\n"
                else:
                    yield f"data: {item}\n\n"
        finally:
            hub.unsubscribe(current_user.id, q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/vapid-public-key", response_model=VapidPublicOut)
async def vapid_public_key():
    if not settings.VAPID_PUBLIC_KEY:
        return VapidPublicOut(public_key="")
    return VapidPublicOut(public_key=settings.VAPID_PUBLIC_KEY)


@router.get("", response_model=List[InAppNotificationOut])
async def list_my_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(InAppNotification).filter(InAppNotification.user_id == current_user.id)
    if unread_only:
        q = q.filter(InAppNotification.read_at.is_(None))
    rows = (
        q.order_by(InAppNotification.created_at.desc()).offset(offset).limit(limit).all()
    )
    return rows


@router.patch("/{notification_id}/read", response_model=InAppNotificationOut)
async def mark_notification_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    n = (
        db.query(InAppNotification)
        .filter(
            InAppNotification.id == notification_id,
            InAppNotification.user_id == current_user.id,
        )
        .first()
    )
    if not n:
        raise HTTPException(status_code=404, detail="Notification not found")
    if n.read_at is None:
        n.read_at = datetime.utcnow()
        db.commit()
        db.refresh(n)
    return n


@router.post("/read-all")
async def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    (
        db.query(InAppNotification)
        .filter(
            InAppNotification.user_id == current_user.id,
            InAppNotification.read_at.is_(None),
        )
        .update({InAppNotification.read_at: datetime.utcnow()}, synchronize_session=False)
    )
    db.commit()
    return {"ok": True}


@router.post("/push-subscription")
async def register_push_subscription(
    body: PushSubscriptionBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not settings.VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=503, detail="Web Push is not configured")
    p256dh = body.keys.get("p256dh")
    auth = body.keys.get("auth")
    if not p256dh or not auth:
        raise HTTPException(status_code=400, detail="keys.p256dh and keys.auth required")

    existing = (
        db.query(PushSubscription).filter(PushSubscription.endpoint == body.endpoint).first()
    )
    if existing:
        existing.user_id = current_user.id
        existing.p256dh = p256dh
        existing.auth = auth
    else:
        db.add(
            PushSubscription(
                user_id=current_user.id,
                endpoint=body.endpoint,
                p256dh=p256dh,
                auth=auth,
            )
        )
    db.commit()
    return {"ok": True}


@router.delete("/push-subscription")
async def remove_push_subscription(
    endpoint: str = Query(..., description="Subscription endpoint URL"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.endpoint == endpoint,
            PushSubscription.user_id == current_user.id,
        )
        .first()
    )
    if sub:
        db.delete(sub)
        db.commit()
    return {"ok": True}
