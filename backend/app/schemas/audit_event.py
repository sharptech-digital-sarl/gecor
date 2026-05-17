from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Any, Dict, Optional
import uuid


class AuditEventOut(BaseModel):
    id: uuid.UUID
    timestamp: datetime
    actor_user_id: Optional[uuid.UUID] = None
    action: str
    resource_type: str
    resource_id: Optional[uuid.UUID] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
