from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.types import TypeDecorator
from datetime import datetime
import enum
import uuid

from app.core.database import Base


class AppointmentTaskStatus(str, enum.Enum):
    OPEN = "open"
    DONE = "done"
    CANCELLED = "cancelled"


def _coerce_task_status(raw) -> AppointmentTaskStatus:
    if raw is None:
        return AppointmentTaskStatus.OPEN
    if isinstance(raw, AppointmentTaskStatus):
        return raw
    s = str(raw).strip()
    if not s:
        return AppointmentTaskStatus.OPEN
    sl = s.lower()
    for m in AppointmentTaskStatus:
        if m.value == sl:
            return m
    try:
        return AppointmentTaskStatus[s.upper()]
    except KeyError:
        pass
    return AppointmentTaskStatus.OPEN


class AppointmentTaskStatusType(TypeDecorator):
    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _coerce_task_status(value).value

    def process_result_value(self, value, dialect):
        return _coerce_task_status(value)


class AppointmentAgendaItem(Base):
    __tablename__ = "appointment_agenda_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=False, index=True)
    sort_order = Column(Integer, nullable=False, default=0)
    title = Column(String(512), nullable=False)
    body = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    appointment = relationship("Appointment", back_populates="agenda_items")


class AppointmentTask(Base):
    __tablename__ = "appointment_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    appointment_id = Column(UUID(as_uuid=True), ForeignKey("appointments.id"), nullable=False, index=True)
    title = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    assignee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    due_at = Column(DateTime, nullable=True)
    status = Column(
        AppointmentTaskStatusType(),
        nullable=False,
        default=AppointmentTaskStatus.OPEN,
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    appointment = relationship("Appointment", back_populates="followup_tasks")
    assignee = relationship("User", foreign_keys=[assignee_id])
