"""visitor photo on visitors; permissions json on roles

Revision ID: add_vphoto_rperms
Revises: 81527ee948d0
Create Date: 2026-03-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


revision = "add_vphoto_rperms"
down_revision = "81527ee948d0"
branch_labels = None
depends_on = None


def _col_exists(table: str, col: str) -> bool:
    bind = op.get_bind()
    ins = inspect(bind)
    if table not in ins.get_table_names():
        return False
    return col in {c["name"] for c in ins.get_columns(table)}


def upgrade() -> None:
    if not _col_exists("visitors", "visitor_photo_path"):
        op.add_column("visitors", sa.Column("visitor_photo_path", sa.String(), nullable=True))
    if not _col_exists("roles", "permissions"):
        op.add_column(
            "roles",
            sa.Column(
                "permissions",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )


def downgrade() -> None:
    if _col_exists("roles", "permissions"):
        op.drop_column("roles", "permissions")
    if _col_exists("visitors", "visitor_photo_path"):
        op.drop_column("visitors", "visitor_photo_path")
