"""Ajoute dashboard.kpi.org aux rôles (volumes organisation) et resynchronise les permissions JSON.

Revision ID: dash_kpi_org
Revises: pwd_reset_2fa_track
"""

import json

from alembic import op
import sqlalchemy as sa

from app.core.permissions import DEFAULT_ROLE_PERMISSIONS

revision = "dash_kpi_org"
down_revision = "pwd_reset_2fa_track"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    for name, perms in DEFAULT_ROLE_PERMISSIONS.items():
        conn.execute(
            sa.text("UPDATE roles SET permissions = CAST(:j AS jsonb) WHERE lower(name) = lower(:n)"),
            {"j": json.dumps(perms), "n": name},
        )


def downgrade() -> None:
    pass
