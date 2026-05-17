"""Synchronise les permissions JSON des rôles (matrice RDV : agenda, secrétaire sans validation DG).

Revision ID: sync_rdv_matrix
Revises: wf_gecor_closed
"""

import json

from alembic import op
import sqlalchemy as sa

from app.core.permissions import DEFAULT_ROLE_PERMISSIONS

revision = "sync_rdv_matrix"
down_revision = "wf_gecor_closed"
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
