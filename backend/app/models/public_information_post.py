from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class PublicInformationPost(Base):
    __tablename__ = "public_information_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)
    published = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_by = relationship("User", foreign_keys=[created_by_id])
