import uuid

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from datetime import datetime
from typing import List, Literal, Optional

BookingSourceType = Literal["internal", "public"]
from app.models.appointment import AppointmentStatus
from app.schemas.email_types import RelaxedEmailStr
from app.schemas.datetime_serialization import datetime_to_iso_utc_z
from app.schemas.user import UserSummary


class ReceptionFinalizeBody(BaseModel):
    internal_notes: Optional[str] = None
    send_visitor_email: bool = True
    force_resend_visitor_email: bool = False


class CheckInResponse(BaseModel):
    message: str
    punctuality_status: Literal["early", "on_time", "late"]
    minutes_delta: int


class AppointmentBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    visitor_name: str
    visitor_email: Optional[RelaxedEmailStr] = None
    visitor_phone: Optional[str] = None
    visitor_company: Optional[str] = None

    @field_serializer("start_time", "end_time")
    def _ser_appointment_bounds(self, v: datetime) -> str:
        return datetime_to_iso_utc_z(v) or ""


class AppointmentCreate(AppointmentBase):
    organizer_id: uuid.UUID
    visitor_photo_base64: Optional[str] = None
    visitor_id_document_base64: Optional[str] = None


class AppointmentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    status: Optional[AppointmentStatus] = None
    visitor_name: Optional[str] = None
    visitor_email: Optional[RelaxedEmailStr] = None
    visitor_phone: Optional[str] = None
    visitor_company: Optional[str] = None
    internal_notes: Optional[str] = None


class AppointmentAgendaItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    appointment_id: uuid.UUID
    sort_order: int
    title: str
    body: Optional[str] = None
    created_at: datetime

    @field_serializer("created_at")
    def _ser_agenda_created(self, v: datetime) -> str:
        return datetime_to_iso_utc_z(v) or ""


class AppointmentTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    appointment_id: uuid.UUID
    title: str
    description: Optional[str] = None
    assignee_id: Optional[uuid.UUID] = None
    due_at: Optional[datetime] = None
    status: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("due_at")
    def _ser_task_due(self, v: datetime | None) -> str | None:
        return datetime_to_iso_utc_z(v)

    @field_serializer("created_at", "updated_at")
    def _ser_task_bounds(self, v: datetime) -> str:
        return datetime_to_iso_utc_z(v) or ""


class ProposeSlotBody(BaseModel):
    proposed_start_time: datetime
    proposed_end_time: datetime


class HierarchyRejectBody(BaseModel):
    """Refus DG après proposition de créneau — annule le RDV."""

    reason: Optional[str] = None


class AppointmentMinutesBody(BaseModel):
    minutes_text: str


class AgendaItemCreate(BaseModel):
    title: str
    body: Optional[str] = None
    sort_order: int = 0


class AgendaItemUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    sort_order: Optional[int] = None


class AppointmentTaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    assignee_id: Optional[uuid.UUID] = None
    due_at: Optional[datetime] = None


class AppointmentTaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[uuid.UUID] = None
    due_at: Optional[datetime] = None
    status: Optional[str] = None


class Appointment(AppointmentBase):
    id: uuid.UUID
    organizer_id: uuid.UUID
    status: AppointmentStatus
    booking_source: BookingSourceType = "internal"
    internal_notes: Optional[str] = None
    reception_validated_at: Optional[datetime] = None
    reception_validated_by_id: Optional[uuid.UUID] = None
    visitor_booking_email_sent_at: Optional[datetime] = None
    reminder_sent: bool
    reminder_sent_at: Optional[datetime] = None
    outlook_event_id: Optional[str] = None
    google_event_id: Optional[str] = None
    synced_with_outlook: bool
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime] = None
    proposed_start_time: Optional[datetime] = None
    proposed_end_time: Optional[datetime] = None
    hierarchy_validated_at: Optional[datetime] = None
    hierarchy_validated_by_id: Optional[uuid.UUID] = None
    minutes_text: Optional[str] = None
    minutes_at: Optional[datetime] = None
    minutes_author_id: Optional[uuid.UUID] = None
    organizer: Optional[UserSummary] = None
    visitor: Optional["Visitor"] = None
    has_pending_deletion_request: bool = False
    highlight_destined: bool = False
    agenda_items: List[AppointmentAgendaItemOut] = Field(default_factory=list)
    followup_tasks: List[AppointmentTaskOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @field_serializer(
        "created_at",
        "updated_at",
        "archived_at",
        "reception_validated_at",
        "visitor_booking_email_sent_at",
        "reminder_sent_at",
        "proposed_start_time",
        "proposed_end_time",
        "hierarchy_validated_at",
        "minutes_at",
    )
    def _ser_appointment_meta(self, v: datetime | None) -> str | None:
        return datetime_to_iso_utc_z(v)


class PublicBookAppointmentResponse(Appointment):
    """Réponse POST /public/book-appointment : PNG du QR en base64 (sans préfixe data URL)."""

    visitor_qr_png_base64: str


class VisitorBase(BaseModel):
    name: str
    email: Optional[RelaxedEmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    id_number: Optional[str] = None


class VisitorCreate(VisitorBase):
    appointment_id: uuid.UUID


class Visitor(VisitorBase):
    id: uuid.UUID
    appointment_id: uuid.UUID
    qr_code_path: Optional[str] = None
    visitor_photo_path: Optional[str] = None
    visitor_id_document_path: Optional[str] = None
    checked_in: bool
    checked_in_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("checked_in_at", "created_at")
    def _ser_visitor_dt(self, v: datetime | None) -> str | None:
        return datetime_to_iso_utc_z(v)
