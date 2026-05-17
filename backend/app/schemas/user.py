from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from datetime import datetime
from typing import List, Literal, Optional
import uuid


class BulkDeleteIds(BaseModel):
    """Liste d’UUID pour suppression en lot (utilisateurs ou groupes)."""

    ids: List[uuid.UUID]

    @field_validator("ids")
    @classmethod
    def unique_and_limit(cls, v: List[uuid.UUID]) -> List[uuid.UUID]:
        if not v:
            raise ValueError("ids must not be empty")
        if len(v) > 500:
            raise ValueError("Maximum 500 ids per request")
        return list(dict.fromkeys(v))
from app.schemas.email_types import RelaxedEmailStr

NotificationSoundPreset = Literal["soft", "standard", "bright", "double"]


class NotificationSoundPrefs(BaseModel):
    """Préférences sons in-app / Web Push (stockées en JSON sur users)."""

    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    mail: NotificationSoundPreset = "standard"
    appointment: NotificationSoundPreset = "standard"
    other: NotificationSoundPreset = "soft"


class NotificationSoundPrefsPatch(BaseModel):
    """PATCH partiel des préférences sons."""

    model_config = ConfigDict(extra="ignore")

    enabled: Optional[bool] = None
    mail: Optional[NotificationSoundPreset] = None
    appointment: Optional[NotificationSoundPreset] = None
    other: Optional[NotificationSoundPreset] = None


class UserBase(BaseModel):
    email: RelaxedEmailStr
    username: str
    full_name: str
    role: str  # nom du rôle en base (y compris groupes personnalisés)
    is_mfa_enabled: bool = False
    google_account_email: Optional[str] = None


class UserCreate(UserBase):
    password: str


class UserAdminCreate(BaseModel):
    """Création d'utilisateur par un master (mot de passe initial)."""

    email: RelaxedEmailStr
    username: str
    full_name: str
    role: str
    password: str

    @field_validator("role")
    @classmethod
    def normalize_role_name(cls, v: str) -> str:
        return v.strip().lower()


class UserUpdate(BaseModel):
    email: Optional[RelaxedEmailStr] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def normalize_role_opt(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.strip().lower()


class UserInDB(UserBase):
    id: uuid.UUID
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    preferred_locale: Optional[Literal["en", "fr"]] = None
    password_must_change: bool = False
    notification_sound_prefs: NotificationSoundPrefs = Field(default_factory=NotificationSoundPrefs)

    @field_validator("notification_sound_prefs", mode="before")
    @classmethod
    def _coerce_notification_sound_prefs(cls, v):
        if v is None:
            return NotificationSoundPrefs()
        if isinstance(v, dict):
            return NotificationSoundPrefs.model_validate(v)
        return v

    class Config:
        from_attributes = True


class MeProfilePatch(BaseModel):
    """PATCH /auth/me — champs modifiables par l’utilisateur connecté."""

    preferred_locale: Optional[Literal["en", "fr"]] = None
    notification_sound_prefs: Optional[NotificationSoundPrefsPatch] = None


class User(UserInDB):
    pass


class UserMe(User):
    """Réponse GET /auth/me : mêmes champs utilisateur + permissions effectives."""

    permissions: List[str] = []


class UserSummary(BaseModel):
    """Simplified user schema for relationships"""
    id: uuid.UUID
    username: str
    full_name: str
    email: RelaxedEmailStr
    role: str

    model_config = ConfigDict(from_attributes=True)


class VisitHostCandidate(BaseModel):
    """Utilisateur pouvant être désigné comme personne sollicitée par un visiteur (hors master)."""

    id: uuid.UUID
    full_name: str
    username: str
    role: str  # valeur enum / nom de rôle (ex. director, secretary)

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    """Login request schema for JSON body"""

    username: str
    password: str

    @field_validator("password")
    @classmethod
    def _normalize_login_password_field(cls, v: str) -> str:
        return str(v).strip()


class Token(BaseModel):
    access_token: str
    token_type: str
    password_change_required: bool = False


class RefreshTokenBody(BaseModel):
    """Corps optionnel lorsque le cookie httpOnly n'est pas envoyé (ex. origine différente)."""

    refresh_token: Optional[str] = None


class LogoutRequest(BaseModel):
    """Révocation de session : cookie et/ou jeton présent en corps."""

    refresh_token: Optional[str] = None


class TokenData(BaseModel):
    user_id: Optional[uuid.UUID] = None


class LoginResponse(BaseModel):
    access_token: Optional[str] = None
    token_type: Optional[str] = None
    mfa_required: bool = False
    mfa_session_id: Optional[uuid.UUID] = None
    password_change_required: bool = False


class AdminPasswordResetRequest(BaseModel):
    """Réinitialisation du mot de passe par un master."""

    mode: Literal["policy", "custom"]
    new_password: Optional[str] = None
    must_change_on_next_login: bool = True

    @model_validator(mode="after")
    def _validate_custom_password(self):
        if self.mode == "custom":
            pw = (self.new_password or "").strip()
            if len(pw) < 8:
                raise ValueError("new_password must be at least 8 characters in custom mode")
            self.new_password = pw
        return self


class AdminPasswordResetOut(BaseModel):
    message: str
    temporary_password: Optional[str] = None


class ChangePasswordStartRequest(BaseModel):
    """Étape 1 : mot de passe actuel + nouveau ; envoie OTP e-mail ou TOTP."""
    current_password: str
    new_password: str

    @field_validator("current_password")
    @classmethod
    def _normalize_current_password(cls, v: str) -> str:
        return str(v).strip()

    @field_validator("new_password")
    @classmethod
    def _min_len(cls, v: str) -> str:
        if len((v or "").strip()) < 8:
            raise ValueError("new_password must be at least 8 characters")
        return v.strip()


class ChangePasswordStartResponse(BaseModel):
    flow: Literal["email_otp", "totp"]
    challenge_id: uuid.UUID
    expires_in_seconds: int
    message: str


class ChangePasswordCompleteRequest(BaseModel):
    challenge_id: uuid.UUID
    code: str

    @field_validator("code")
    @classmethod
    def _digits(cls, v: str) -> str:
        s = "".join(c for c in str(v) if c.isdigit())
        if len(s) != 6:
            raise ValueError("code must be 6 digits")
        return s


class MFASetupResponse(BaseModel):
    secret: str
    otpauth_url: str


class MFAActivateRequest(BaseModel):
    code: str


class MFAVerifyRequest(BaseModel):
    mfa_session_id: uuid.UUID
    code: str

