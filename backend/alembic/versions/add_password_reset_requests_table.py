"""Table password_reset_requests (mot de passe oublié, rappels master).

Revision ID: pwd_reset_reqs
Revises: user_pwd_must_change
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "pwd_reset_reqs"
down_revision = "user_pwd_must_change"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email_requested", sa.String(), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("requester_message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("last_master_reminder_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolved_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_password_reset_requests_email", "password_reset_requests", ["email_requested"])
    op.create_index("ix_password_reset_requests_status", "password_reset_requests", ["status"])
    op.create_index("ix_password_reset_requests_created", "password_reset_requests", ["created_at"])
    op.alter_column("password_reset_requests", "status", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_password_reset_requests_created", table_name="password_reset_requests")
    op.drop_index("ix_password_reset_requests_status", table_name="password_reset_requests")
    op.drop_index("ix_password_reset_requests_email", table_name="password_reset_requests")
    op.drop_table("password_reset_requests")
