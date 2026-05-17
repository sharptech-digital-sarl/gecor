from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator
from datetime import datetime
import enum
import uuid

from app.core.database import Base

_APPT_ENUM = lambda cls: [e.value for e in cls]


class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    SLOT_PROPOSED = "slot_proposed"
    PENDING_AUTHORIZATION = "pending_authorization"
    PREPARATION = "preparation"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


def _coerce_appointment_status(raw) -> AppointmentStatus:
    """Ancien enum PG appointmentstatus : souvent PENDING (nom) au lieu de pending (valeur)."""
    if raw is None:
        return AppointmentStatus.PENDING
    if isinstance(raw, AppointmentStatus):
        return raw
    s = str(raw).strip()
    if not s:
        return AppointmentStatus.PENDING
    sl = s.lower()
    for m in AppointmentStatus:
        if m.value == sl:
            return m
    try:
        return AppointmentStatus[s.upper()]
    except KeyError:
        pass
    return AppointmentStatus.PENDING


class AppointmentStatusType(TypeDecorator):
    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _coerce_appointment_status(value).value

    def process_result_value(self, value, dialect):
        return _coerce_appointment_status(value)


class BookingSource(str, enum.Enum):
    INTERNAL = "internal"
    PUBLIC = "public"


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False, index=True)
    location = Column(String, nullable=True)

    status = Column(
        AppointmentStatusType(),
        default=AppointmentStatus.PENDING,
        nullable=False,
    )

    organizer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    visitor_name = Column(String, nullable=False)
    visitor_email = Column(String, nullable=True)
    visitor_phone = Column(String, nullable=True)
    visitor_company = Column(String, nullable=True)

    reminder_sent = Column(Boolean, default=False)
    reminder_sent_at = Column(DateTime, nullable=True)

    outlook_event_id = Column(String, nullable=True, unique=True, index=True)
    synced_with_outlook = Column(Boolean, default=False)
    google_event_id = Column(String, nullable=True, unique=True, index=True)
    last_sync_at = Column(DateTime, nullable=True)

    booking_source = Column(String(32), default=BookingSource.INTERNAL.value, nullable=False)
    internal_notes = Column(Text, nullable=True)
    reception_validated_at = Column(DateTime, nullable=True)
    reception_validated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    visitor_booking_email_sent_at = Column(DateTime, nullable=True)

    proposed_start_time = Column(DateTime, nullable=True)
    proposed_end_time = Column(DateTime, nullable=True)
    hierarchy_validated_at = Column(DateTime, nullable=True)
    hierarchy_validated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    minutes_text = Column(Text, nullable=True)
    minutes_at = Column(DateTime, nullable=True)
    minutes_author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    archived_at = Column(DateTime, nullable=True, index=True)

    organizer = relationship("User", back_populates="appointments", foreign_keys=[organizer_id])
    reception_validated_by = relationship("User", foreign_keys=[reception_validated_by_id])
    hierarchy_validated_by = relationship("User", foreign_keys=[hierarchy_validated_by_id])
    minutes_author = relationship("User", foreign_keys=[minutes_author_id])
    visitor = relationship("Visitor", back_populates="appointment", uselist=False, cascade="all, delete-orphan")
    agenda_items = relationship(
        "AppointmentAgendaItem",
        back_populates="appointment",
        cascade="all, delete-orphan",
        order_by="AppointmentAgendaItem.sort_order",
    )
    followup_tasks = relationship(
        "AppointmentTask",
        back_populates="appointment",
        cascade="all, delete-orphan",
    )


class Visitor(Base):
    __tablename__ = "visitors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=False, unique=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    company = Column(String, nullable=True)
    id_number = Column(String, nullable=True)
    qr_code_path = Column(String, nullable=True)
    visitor_photo_path = Column(String, nullable=True)
    visitor_id_document_path = Column(String, nullable=True)
    checked_in = Column(Boolean, default=False)
    checked_in_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    appointment = relationship("Appointment", back_populates="visitor")
