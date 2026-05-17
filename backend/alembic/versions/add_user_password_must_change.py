"""Add password_must_change flag on users (admin reset / force change on login).

Revision ID: user_pwd_must_change
Revises: appt_archived_at
"""

from alembic import op
import sqlalchemy as sa

revision = "user_pwd_must_change"
down_revision = "appt_archived_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("password_must_change", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("users", "password_must_change", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "password_must_change")
