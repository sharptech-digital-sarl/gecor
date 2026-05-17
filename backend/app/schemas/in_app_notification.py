from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Any, Dict, Optional
import uuid


class InAppNotificationOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    body: str
    payload: Optional[Dict[str, Any]] = None
    read_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PushSubscriptionBody(BaseModel):
    endpoint: str
    keys: Dict[str, str]  # p256dh, auth


class VapidPublicOut(BaseModel):
    public_key: str
