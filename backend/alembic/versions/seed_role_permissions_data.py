"""Seed default JSON permissions per role name

Revision ID: seed_rperms_data
Revises: add_vphoto_rperms
Create Date: 2026-03-29

"""
import json

from alembic import op
import sqlalchemy as sa

from app.core.permissions import DEFAULT_ROLE_PERMISSIONS

revision = "seed_rperms_data"
down_revision = "add_vphoto_rperms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    for name, perms in DEFAULT_ROLE_PERMISSIONS.items():
        conn.execute(
            sa.text(
                "UPDATE roles SET permissions = CAST(:j AS jsonb) WHERE lower(name) = lower(:n)"
            ),
            {"j": json.dumps(perms), "n": name},
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE roles SET permissions = '[]'::jsonb"))
