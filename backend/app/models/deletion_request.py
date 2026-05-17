import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

# Valeurs stables (pas d'ENUM SQL pour simplifier les migrations)
TARGET_MAIL = "mail_document"
TARGET_APPOINTMENT = "appointment"
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"


class DeletionRequest(Base):
    __tablename__ = "deletion_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    target_type = Column(String(32), nullable=False, index=True)
    target_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    reason = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default=STATUS_PENDING, index=True)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
