import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class PasswordResetChallengeKind(str, enum.Enum):
    EMAIL_OTP = "email_otp"
    TOTP = "totp"
    PASSWORD_CHANGE_EMAIL_OTP = "password_change_email_otp"
    PASSWORD_CHANGE_TOTP = "password_change_totp"


class PasswordResetChallenge(Base):
    """Étape 2FA avant création d'une PasswordResetRequest (OTP e-mail ou TOTP)."""

    __tablename__ = "password_reset_challenges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    email_normalized = Column(String, nullable=False, index=True)
    kind = Column(String(32), nullable=False)
    otp_code_hash = Column(String(128), nullable=True)
    # Changement de mot de passe (utilisateur connecté) : hash bcrypt du nouveau mot de passe, appliqué après OTP/TOTP.
    pending_password_hash = Column(String(255), nullable=True)
    requester_message = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    consumed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", foreign_keys=[user_id])
