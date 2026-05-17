from datetime import datetime
from typing import Literal, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.email_types import RelaxedEmailStr


class ForgotPasswordStartRequest(BaseModel):
    email: RelaxedEmailStr
    message: Optional[str] = Field(None, max_length=2000)


class ForgotPasswordStartResponse(BaseModel):
    """Étape 1 : noop si pas de compte ; sinon challenge e-mail ou TOTP."""

    flow: Literal["noop", "email_otp", "totp"]
    message: str
    challenge_id: Optional[uuid.UUID] = None
    expires_in_seconds: Optional[int] = None


class ForgotPasswordVerifyRequest(BaseModel):
    challenge_id: uuid.UUID
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class ForgotPasswordVerifyResponse(BaseModel):
    message: str


class PasswordResetRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email_requested: str
    user_id: Optional[uuid.UUID] = None
    requester_username: Optional[str] = None
    requester_full_name: Optional[str] = None
    requester_message: Optional[str] = None
    status: str
    created_at: datetime
    last_master_reminder_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None
    password_reset_at: Optional[datetime] = None
    password_reset_mode: Optional[str] = None
    password_reset_must_change: Optional[bool] = None


class PasswordResetRequestResolve(BaseModel):
    action: Literal["completed", "rejected"]
    note: Optional[str] = Field(None, max_length=2000)
