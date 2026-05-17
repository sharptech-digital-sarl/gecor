"""visitors.visitor_id_document_path — copy of ID document image

Revision ID: visitor_id_doc
Revises: plan_audit_notify
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "visitor_id_doc"
down_revision = "plan_audit_notify"
branch_labels = None
depends_on = None


def _column_exists(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table(table):
        return False
    return col in [c["name"] for c in insp.get_columns(table)]


def upgrade() -> None:
    if not _column_exists("visitors", "visitor_id_document_path"):
        op.add_column(
            "visitors",
            sa.Column("visitor_id_document_path", sa.String(), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("visitors", "visitor_id_document_path"):
        op.drop_column("visitors", "visitor_id_document_path")
