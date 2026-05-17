"""Sync director/admin role permissions (mail.delete, appointments.delete).

Revision ID: grant_del_dir_admin
Revises: add_del_reqs
Create Date: 2026-03-31

"""
import json

from alembic import op
import sqlalchemy as sa

from app.core.permissions import DEFAULT_ROLE_PERMISSIONS

revision = "grant_del_dir_admin"
down_revision = "add_del_reqs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    for role_name in ("director", "admin"):
        perms = DEFAULT_ROLE_PERMISSIONS.get(role_name)
        if not perms:
            continue
        j = json.dumps(perms)
        conn.execute(
            sa.text("UPDATE roles SET permissions = CAST(:j AS jsonb) WHERE lower(name) = lower(:n)"),
            {"j": j, "n": role_name},
        )

    exists = conn.execute(sa.text("SELECT 1 FROM roles WHERE lower(name) = 'admin' LIMIT 1")).scalar()
    if not exists:
        j = json.dumps(DEFAULT_ROLE_PERMISSIONS["admin"])
        conn.execute(
            sa.text(
                """
                INSERT INTO roles (id, name, description, permissions, created_at, updated_at)
                VALUES (gen_random_uuid(), 'admin', :d, CAST(:j AS jsonb), NOW(), NOW())
                """
            ),
            {
                "d": "Administrateur (mêmes droits que directeur, dont suppressions).",
                "j": j,
            },
        )


def downgrade() -> None:
    pass
