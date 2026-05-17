"""Règles SLA (délais de traitement) par type d'entité et critères."""

from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.core.database import Base


class SlaRule(Base):
    __tablename__ = "sla_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    entity_type = Column(String(32), nullable=False, index=True)  # mail
    qualification = Column(String(64), nullable=True, index=True)
    priority = Column(String(32), nullable=True, index=True)
    hours_allowed = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
