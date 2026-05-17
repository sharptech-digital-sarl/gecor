from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from app.models.mail import MailStatus, MailDirection, MailChannel, MailQualification


class MailDocumentBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "normal"


class MailDocumentCreate(MailDocumentBase):
    file_name: str
    file_size: int
    mime_type: str
    response_deadline: Optional[datetime] = None


class MailDocumentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[uuid.UUID] = None
    priority: Optional[str] = None
    response_deadline: Optional[datetime] = None
    direction: Optional[MailDirection] = None
    channel: Optional[MailChannel] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    sender_phone: Optional[str] = None
    qualification: Optional[MailQualification] = None
    tags: Optional[List[str]] = None
    intended_send_channel: Optional[str] = None
    sent_at: Optional[datetime] = None
    outbound_send_status: Optional[str] = None
    current_department: Optional[str] = None


class MailTransitionRequest(BaseModel):
    action_key: str
    notes: Optional[str] = None
    assigned_to_id: Optional[uuid.UUID] = None
    current_department: Optional[str] = Field(
        None,
        description="Service / direction cible (ex. orientation par la secrétaire lors de l’affectation).",
    )


class MailAvailableActionOut(BaseModel):
    action_key: str
    to_status: str
    label: str
    requires_assignee: bool


class MailDocument(MailDocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference_number: str
    file_path: str
    file_name: str
    file_size: int
    mime_type: str
    ocr_text: Optional[str] = None
    ocr_keywords: Optional[List[str]] = None
    ocr_processed: bool
    status: MailStatus
    direction: MailDirection
    channel: Optional[MailChannel] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    sender_phone: Optional[str] = None
    qualification: Optional[MailQualification] = None
    tags: Optional[List[Any]] = None
    current_department: Optional[str] = None
    priority: str
    intended_send_channel: Optional[str] = None
    sent_at: Optional[datetime] = None
    outbound_send_status: Optional[str] = None
    workflow_definition_id: Optional[uuid.UUID] = None
    created_by: uuid.UUID
    assigned_to: Optional[uuid.UUID] = None
    response_deadline: Optional[datetime] = None
    is_overdue: bool
    created_at: datetime
    updated_at: datetime
    has_pending_deletion_request: bool = False
    highlight_destined: bool = False

    @model_validator(mode="after")
    def _default_tags(self):
        if self.tags is None:
            object.__setattr__(self, "tags", [])
        return self


class MailSearchResponse(BaseModel):
    """Réponse de l'endpoint /api/v1/mail/search : items + total + facettes."""

    items: List["MailDocument"]
    total: int
    skip: int
    limit: int
    facets: Dict[str, Dict[str, int]] = Field(
        default_factory=dict,
        description=(
            "Agrégats par statut, direction, qualification (sur l'ensemble filtré, "
            "pas seulement la page en cours)."
        ),
    )


MailSearchResponse.model_rebuild()


class MailVersion(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    file_path: str
    change_description: Optional[str] = None
    created_by: uuid.UUID
    created_at: datetime


class WorkflowState(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    document_id: uuid.UUID
    status: MailStatus
    department: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


class WorkflowHistory(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    document_id: uuid.UUID
    from_status: Optional[MailStatus] = None
    to_status: MailStatus
    action: str
    performed_by: uuid.UUID
    notes: Optional[str] = None
    created_at: datetime
