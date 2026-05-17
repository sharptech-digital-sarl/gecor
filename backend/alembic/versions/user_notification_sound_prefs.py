"""Colonne JSON notification_sound_prefs sur users.

Revision ID: user_notif_sound_prefs
Revises: dash_kpi_org
"""

from alembic import op
import sqlalchemy as sa

revision = "user_notif_sound_prefs"
down_revision = "dash_kpi_org"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("notification_sound_prefs", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "notification_sound_prefs")
