from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.core.database import Base


class NotificationType(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    SYSTEM = "system"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)  # Null for external recipients
    recipient_email = Column(String, nullable=True)
    recipient_phone = Column(String, nullable=True)
    
    notification_type = Column(Enum(NotificationType), nullable=False)
    status = Column(Enum(NotificationStatus), default=NotificationStatus.PENDING, nullable=False)
    
    subject = Column(String, nullable=True)
    message = Column(Text, nullable=False)
    template_name = Column(String, nullable=True)
    
    # Related entities
    related_document_id = Column(UUID(as_uuid=True), ForeignKey("mail_documents.id"), nullable=True)
    related_appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=True)
    
    # Delivery tracking
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    recipient = relationship("User")

