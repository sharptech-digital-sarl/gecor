"""deletion_requests table; refresh role permissions JSON

Revision ID: add_del_reqs
Revises: seed_rperms_data
Create Date: 2026-03-29

"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import inspect

from app.core.permissions import DEFAULT_ROLE_PERMISSIONS

revision = "add_del_reqs"
down_revision = "seed_rperms_data"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return name in inspect(bind).get_table_names()


def upgrade() -> None:
    if not _table_exists("deletion_requests"):
        op.create_table(
            "deletion_requests",
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("target_type", sa.String(32), nullable=False, index=True),
            sa.Column("target_id", UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, index=True),
            sa.Column("requested_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("resolved_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("resolution_notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index(
            "ix_deletion_requests_pending_target",
            "deletion_requests",
            ["target_type", "target_id"],
            unique=True,
            postgresql_where=sa.text("status = 'pending'"),
        )

    conn = op.get_bind()
    for name, perms in DEFAULT_ROLE_PERMISSIONS.items():
        conn.execute(
            sa.text(
                "UPDATE roles SET permissions = CAST(:j AS jsonb) WHERE lower(name) = lower(:n)"
            ),
            {"j": json.dumps(perms), "n": name},
        )


def downgrade() -> None:
    if _table_exists("deletion_requests"):
        op.drop_index("ix_deletion_requests_pending_target", table_name="deletion_requests")
        op.drop_table("deletion_requests")
