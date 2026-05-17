"""2FA challenges for forgot-password; track master password reset on requests.

Revision ID: pwd_reset_2fa_track
Revises: pwd_reset_reqs
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "pwd_reset_2fa_track"
down_revision = "pwd_reset_reqs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_challenges",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("email_normalized", sa.String(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("otp_code_hash", sa.String(128), nullable=True),
        sa.Column("requester_message", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_pwd_reset_chal_user", "password_reset_challenges", ["user_id"])
    op.create_index("ix_pwd_reset_chal_email", "password_reset_challenges", ["email_normalized"])
    op.create_index("ix_pwd_reset_chal_exp", "password_reset_challenges", ["expires_at"])
    op.alter_column("password_reset_challenges", "consumed", server_default=None)

    op.add_column(
        "password_reset_requests",
        sa.Column("password_reset_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "password_reset_requests",
        sa.Column("password_reset_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("password_reset_requests", sa.Column("password_reset_mode", sa.String(32), nullable=True))
    op.add_column(
        "password_reset_requests",
        sa.Column("password_reset_must_change", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("password_reset_requests", "password_reset_must_change")
    op.drop_column("password_reset_requests", "password_reset_mode")
    op.drop_column("password_reset_requests", "password_reset_by_user_id")
    op.drop_column("password_reset_requests", "password_reset_at")
    op.drop_index("ix_pwd_reset_chal_exp", table_name="password_reset_challenges")
    op.drop_index("ix_pwd_reset_chal_email", table_name="password_reset_challenges")
    op.drop_index("ix_pwd_reset_chal_user", table_name="password_reset_challenges")
    op.drop_table("password_reset_challenges")
