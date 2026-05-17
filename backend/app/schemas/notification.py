from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid
from app.models.notification import NotificationType, NotificationStatus
from app.schemas.email_types import RelaxedEmailStr


class NotificationBase(BaseModel):
    notification_type: NotificationType
    subject: Optional[str] = None
    message: str
    template_name: Optional[str] = None


class NotificationCreate(NotificationBase):
    recipient_id: Optional[uuid.UUID] = None
    recipient_email: Optional[RelaxedEmailStr] = None
    recipient_phone: Optional[str] = None
    related_document_id: Optional[uuid.UUID] = None
    related_appointment_id: Optional[uuid.UUID] = None


class Notification(NotificationBase):
    id: uuid.UUID
    recipient_id: Optional[uuid.UUID] = None
    recipient_email: Optional[RelaxedEmailStr] = None
    recipient_phone: Optional[str] = None
    status: NotificationStatus
    related_document_id: Optional[uuid.UUID] = None
    related_appointment_id: Optional[uuid.UUID] = None
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime

    class Config:
        from_attributes = True

