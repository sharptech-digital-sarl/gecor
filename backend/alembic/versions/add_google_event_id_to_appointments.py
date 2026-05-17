"""add google event id to appointments

Revision ID: add_google_event_id
Revises: grant_del_dir_admin
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_google_event_id"
down_revision = "grant_del_dir_admin"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def _index_exists(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    if not _column_exists("appointments", "google_event_id"):
        op.add_column("appointments", sa.Column("google_event_id", sa.String(), nullable=True))
    if not _index_exists("appointments", "ix_appointments_google_event_id"):
        op.create_index("ix_appointments_google_event_id", "appointments", ["google_event_id"], unique=True)


def downgrade() -> None:
    if _index_exists("appointments", "ix_appointments_google_event_id"):
        op.drop_index("ix_appointments_google_event_id", table_name="appointments")
    if _column_exists("appointments", "google_event_id"):
        op.drop_column("appointments", "google_event_id")
