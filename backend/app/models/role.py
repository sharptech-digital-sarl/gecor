from sqlalchemy import Column, String, DateTime, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, unique=True, nullable=False, index=True)  # master, director, secretary, etc.
    description = Column(String, nullable=True)
    permissions = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to users through junction table
    users = relationship("User", secondary="user_roles", back_populates="roles")

