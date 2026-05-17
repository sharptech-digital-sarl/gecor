from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String(128), nullable=False, index=True)
    resource_type = Column(String(128), nullable=False)
    resource_id = Column(UUID(as_uuid=True), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(512), nullable=True)

    actor = relationship("User", foreign_keys=[actor_user_id])
