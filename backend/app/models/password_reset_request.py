import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class PasswordResetRequestStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    REJECTED = "rejected"


class PasswordResetRequest(Base):
    """Demande « mot de passe oublié » saisie sur la page publique ; traitée par le master."""

    __tablename__ = "password_reset_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email_requested = Column(String, nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    requester_message = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default=PasswordResetRequestStatus.PENDING.value, index=True)
    last_master_reminder_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    password_reset_at = Column(DateTime, nullable=True)
    password_reset_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    password_reset_mode = Column(String(32), nullable=True)
    password_reset_must_change = Column(Boolean, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id])
    password_reset_by = relationship("User", foreign_keys=[password_reset_by_user_id])
