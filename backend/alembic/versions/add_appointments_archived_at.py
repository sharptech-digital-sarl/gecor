"""Add archived_at to appointments (soft archive, excluded from KPIs and conflicts).

Revision ID: appt_archived_at
Revises: sync_rdv_matrix
"""

from alembic import op
import sqlalchemy as sa

revision = "appt_archived_at"
down_revision = "sync_rdv_matrix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("appointments", sa.Column("archived_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("appointments", "archived_at")
