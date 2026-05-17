"""pending_password_hash sur password_reset_challenges (changement mot de passe authentifié).

Revision ID: pending_pwd_hash_ch
Revises: user_notif_sound_prefs
"""

from alembic import op
import sqlalchemy as sa

revision = "pending_pwd_hash_ch"
down_revision = "user_notif_sound_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "password_reset_challenges",
        sa.Column("pending_password_hash", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("password_reset_challenges", "pending_password_hash")
