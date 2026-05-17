"""Ajout preferred_locale sur users (e-mails i18n).

Revision ID: add_user_preferred_locale
Revises: ged_enrichment_v1
"""

from alembic import op
import sqlalchemy as sa

revision = "add_user_preferred_locale"
down_revision = "ged_enrichment_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("preferred_locale", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "preferred_locale")
