from sqlalchemy import Column, ForeignKey, DateTime, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from app.core.database import Base


# Junction table for many-to-many relationship between users and roles
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("created_at", DateTime, default=datetime.utcnow),
    # Ensure one user can't have the same role twice
    UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    comment="Junction table linking users to roles"
)

