from sqlalchemy import Column, String, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
import uuid

from app.core.database import Base


# Keep UserRole enum for backward compatibility in code (not used in database anymore)
class UserRole(str, enum.Enum):
    MASTER = "master"  # Replaces admin - has full access
    DIRECTOR = "director"
    SECRETARY = "secretary"
    ANALYST = "analyst"
    RECEPTIONIST = "receptionist"
    GUEST = "guest"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    # role column removed - now using many-to-many relationship with roles table
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    is_mfa_enabled = Column(Boolean, default=False, nullable=False)
    mfa_secret = Column(String, nullable=True)
    mfa_temp_secret = Column(String, nullable=True)
    google_refresh_token = Column(String, nullable=True)
    google_access_token = Column(String, nullable=True)
    google_access_token_expires_at = Column(DateTime, nullable=True)
    google_account_email = Column(String, nullable=True)
    # Langue des e-mails transactionnels (fr | en). Null = DEFAULT_NOTIFICATION_LOCALE côté config.
    preferred_locale = Column(String(10), nullable=True)
    # Préférences sons notifications : enabled, mail, appointment, other (presets soft|standard|bright|double).
    notification_sound_prefs = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    password_must_change = Column(Boolean, default=False, nullable=False)

    # Relationships
    roles = relationship("Role", secondary="user_roles", back_populates="users")
    created_mail_documents = relationship("MailDocument", back_populates="created_by_user", foreign_keys="MailDocument.created_by")
    assigned_mail_documents = relationship("MailDocument", back_populates="assigned_to_user", foreign_keys="MailDocument.assigned_to")
    appointments = relationship(
        "Appointment",
        back_populates="organizer",
        foreign_keys="Appointment.organizer_id",
    )
    signatures = relationship("Signature", back_populates="user")
    sessions = relationship("SessionToken", back_populates="user", cascade="all, delete-orphan")
    mfa_sessions = relationship("MfaSession", back_populates="user", cascade="all, delete-orphan")
    
    # Helper property for backward compatibility (API / JWT : nom du rôle en base)
    @property
    def role(self) -> str:
        """Premier rôle assigné (nom en minuscules), ex. master, secretary, ou groupe personnalisé."""
        if hasattr(self, '_sa_instance_state'):
            _ = self.roles
        if self.roles:
            return self.roles[0].name.lower()
        return UserRole.GUEST.value
    
    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role by name."""
        return any(role.name.lower() == role_name.lower() for role in self.roles)
    
    def has_any_role(self, *role_names: str) -> bool:
        """Check if user has any of the specified roles."""
        user_role_names = {role.name.lower() for role in self.roles}
        return any(role_name.lower() in user_role_names for role_name in role_names)

