from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, Dict, Any
import uuid


class SignatureBase(BaseModel):
    comments: Optional[str] = None
    annotations: Optional[Dict[str, Any]] = None


class SignatureCreate(SignatureBase):
    document_id: uuid.UUID
    signature_data: str  # Base64 encoded signature image (data URL or base64)


class Signature(SignatureBase):
    id: uuid.UUID
    document_id: uuid.UUID
    user_id: uuid.UUID
    signature_image_path: str
    signature_data: Optional[str] = None  # Data URL format: data:image/png;base64,...
    signed_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    @field_validator('signature_data', mode='before')
    @classmethod
    def ensure_data_url(cls, v):
        """Ensure signature_data is in data URL format"""
        if v is None:
            return None
        # If it's already a data URL, return as is
        if isinstance(v, str) and v.startswith('data:image/'):
            return v
        # If it's base64 without prefix, add the prefix
        if isinstance(v, str) and not v.startswith('data:'):
            return f"data:image/png;base64,{v}"
        return v

    class Config:
        from_attributes = True

