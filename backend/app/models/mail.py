from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON, Boolean, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator
from datetime import datetime
import enum
import uuid

from app.core.database import Base

_ENUM_STR = lambda cls: [e.value for e in cls]


class MailStatus(str, enum.Enum):
    RECEIVED = "received"
    INDEXED = "indexed"
    ASSIGNED = "assigned"
    IN_TREATMENT = "in_treatment"
    # Avis direction (chef de service / secrétariat direction) avant transmission au DG
    PENDING_DIRECTOR = "pending_director"
    PENDING_VALIDATION = "pending_validation"
    ON_HOLD = "on_hold"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"  # Clôturé (post-validation DG), avant archivage définitif
    ARCHIVED = "archived"


class MailDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"


class MailChannel(str, enum.Enum):
    SCAN = "scan"
    EMAIL = "email"
    PLATFORM = "platform"


class MailQualification(str, enum.Enum):
    ADMINISTRATIVE = "administrative"
    FINANCIAL = "financial"
    HR = "hr"
    LEGAL = "legal"
    OTHER = "other"


def _coerce_mail_status(raw) -> MailStatus:
    """Accepte valeurs courantes, noms PG historiques (RECEIVED) et ancien in_review."""
    if raw is None:
        return MailStatus.RECEIVED
    if isinstance(raw, MailStatus):
        return raw
    s = str(raw).strip()
    if not s:
        return MailStatus.RECEIVED
    sl = s.lower()
    if sl == "in_review":
        return MailStatus.IN_TREATMENT
    for m in MailStatus:
        if m.value == sl:
            return m
    try:
        return MailStatus[s.upper()]
    except KeyError:
        pass
    return MailStatus.RECEIVED


class MailStatusType(TypeDecorator):
    """VARCHAR / enum PG legacy : évite LookupError quand la base renvoie RECEIVED au lieu de received."""

    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _coerce_mail_status(value).value

    def process_result_value(self, value, dialect):
        return _coerce_mail_status(value)


class MailDocument(Base):
    __tablename__ = "mail_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    reference_number = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String, nullable=False)

    # OCR Data
    ocr_text = Column(Text, nullable=True)
    ocr_keywords = Column(JSON, nullable=True)
    ocr_processed = Column(Boolean, default=False)
    ocr_processed_at = Column(DateTime, nullable=True)

    # GED / workflow
    status = Column(
        MailStatusType(),
        default=MailStatus.RECEIVED,
        nullable=False,
    )
    direction = Column(
        Enum(MailDirection, native_enum=False, values_callable=_ENUM_STR),
        default=MailDirection.INBOUND,
        nullable=False,
        index=True,
    )
    channel = Column(
        Enum(MailChannel, native_enum=False, values_callable=_ENUM_STR),
        nullable=True,
    )
    sender_name = Column(String(255), nullable=True)
    sender_email = Column(String(255), nullable=True)
    sender_phone = Column(String(64), nullable=True)
    qualification = Column(
        Enum(MailQualification, native_enum=False, values_callable=_ENUM_STR),
        nullable=True,
        index=True,
    )
    tags = Column(JSONB, nullable=True, server_default=text("'[]'::jsonb"))

    current_department = Column(String, nullable=True)
    priority = Column(String, default="normal")

    # Sortant
    intended_send_channel = Column(String(64), nullable=True)
    sent_at = Column(DateTime, nullable=True)
    outbound_send_status = Column(String(32), nullable=True)

    workflow_definition_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_definitions.id"),
        nullable=True,
        index=True,
    )

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    response_deadline = Column(DateTime, nullable=True)
    is_overdue = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    archived_at = Column(DateTime, nullable=True)

    created_by_user = relationship("User", foreign_keys=[created_by], back_populates="created_mail_documents")
    assigned_to_user = relationship("User", foreign_keys=[assigned_to], back_populates="assigned_mail_documents")
    workflow_definition = relationship("WorkflowDefinition")
    versions = relationship("MailVersion", back_populates="document", cascade="all, delete-orphan")
    workflow_states = relationship("WorkflowState", back_populates="document", cascade="all, delete-orphan")
    workflow_history = relationship("WorkflowHistory", back_populates="document", cascade="all, delete-orphan")
    signatures = relationship("Signature", back_populates="document")


class MailVersion(Base):
    __tablename__ = "mail_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("mail_documents.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    file_path = Column(String, nullable=False)
    change_description = Column(Text, nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("MailDocument", back_populates="versions")


class WorkflowState(Base):
    __tablename__ = "workflow_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("mail_documents.id"), nullable=False)
    status = Column(MailStatusType(), nullable=False)
    department = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("MailDocument", back_populates="workflow_states")


class WorkflowHistory(Base):
    __tablename__ = "workflow_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("mail_documents.id"), nullable=False)
    from_status = Column(MailStatusType(), nullable=True)
    to_status = Column(MailStatusType(), nullable=False)
    action = Column(String, nullable=False)
    performed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("MailDocument", back_populates="workflow_history")
