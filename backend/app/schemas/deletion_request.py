from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict


class DeletionRequestOut(BaseModel):
    id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    reason: Optional[str] = None
    status: str
    requested_by: uuid.UUID
    resolved_by: Optional[uuid.UUID] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeletionRequestCreateBody(BaseModel):
    reason: Optional[str] = None


class DeletionResolveBody(BaseModel):
    resolution_notes: Optional[str] = None
