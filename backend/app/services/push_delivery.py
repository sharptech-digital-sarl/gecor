import json
import logging
from typing import Any, Dict, Optional, Set
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.push_subscription import PushSubscription
from app.services.notification_sound_category import sound_category_for_payload

logger = logging.getLogger(__name__)


def deliver_web_push_to_users(
    db: Session,
    user_ids: Set[UUID],
    title: str,
    body: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        return
    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        return

    subs = (
        db.query(PushSubscription).filter(PushSubscription.user_id.in_(list(user_ids))).all()
    )
    if not subs:
        return

    data_obj: Dict[str, Any] = {"title": title, "body": body}
    if payload:
        data_obj.update(payload)
    data_obj["sound_category"] = sound_category_for_payload(payload)
    pdata = json.dumps(data_obj)

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=pdata,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_SUBJECT},
            )
        except WebPushException as e:
            if getattr(e, "response", None) is not None and e.response.status_code in (404, 410):
                db.delete(sub)
                db.commit()
            logger.warning("WebPush failed: %s", e, exc_info=False)
        except Exception as e:
            logger.warning("WebPush error: %s", e, exc_info=False)
