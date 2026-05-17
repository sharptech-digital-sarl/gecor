from sqlalchemy import Column, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.core.database import Base


class Signature(Base):
    __tablename__ = "signatures"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("mail_documents.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Signature data
    signature_image_path = Column(String, nullable=False)  # Path to signature image
    signature_data = Column(Text, nullable=True)  # Base64 or JSON signature data
    
    # Annotations
    annotations = Column(JSON, nullable=True)  # Array of annotation objects
    comments = Column(Text, nullable=True)
    
    # Metadata
    signed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    
    # Relationships
    document = relationship("MailDocument", back_populates="signatures")
    user = relationship("User", back_populates="signatures")

