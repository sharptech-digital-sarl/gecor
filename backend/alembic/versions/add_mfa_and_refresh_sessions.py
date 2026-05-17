"""add mfa fields and refresh sessions

Revision ID: add_mfa_and_refresh_sessions
Revises: convert_ids_to_uuid
Create Date: 2025-12-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "add_mfa_and_refresh_sessions"
down_revision = "convert_ids_to_uuid"
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # Add MFA columns to users table if they don't exist
    if not column_exists("users", "is_mfa_enabled"):
        op.add_column("users", sa.Column("is_mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        op.alter_column("users", "is_mfa_enabled", server_default=None)
    if not column_exists("users", "mfa_secret"):
        op.add_column("users", sa.Column("mfa_secret", sa.String(), nullable=True))
    if not column_exists("users", "mfa_temp_secret"):
        op.add_column("users", sa.Column("mfa_temp_secret", sa.String(), nullable=True))
    if not column_exists("users", "google_refresh_token"):
        op.add_column("users", sa.Column("google_refresh_token", sa.String(), nullable=True))
    if not column_exists("users", "google_access_token"):
        op.add_column("users", sa.Column("google_access_token", sa.String(), nullable=True))
    if not column_exists("users", "google_access_token_expires_at"):
        op.add_column("users", sa.Column("google_access_token_expires_at", sa.DateTime(), nullable=True))
    if not column_exists("users", "google_account_email"):
        op.add_column("users", sa.Column("google_account_email", sa.String(), nullable=True))

    # Create session_tokens table if it doesn't exist
    if not table_exists("session_tokens"):
        op.create_table(
            "session_tokens",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("refresh_token_hash", sa.String(), nullable=False),
            sa.Column("user_agent", sa.String(), nullable=True),
            sa.Column("ip_address", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
        )

        op.create_index("ix_session_tokens_user_id", "session_tokens", ["user_id"])
        op.create_index("ix_session_tokens_refresh_token_hash", "session_tokens", ["refresh_token_hash"])
        op.create_index("ix_session_tokens_id", "session_tokens", ["id"])

    # Create mfa_sessions table if it doesn't exist
    if not table_exists("mfa_sessions"):
        op.create_table(
            "mfa_sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("is_consumed", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

        op.create_index("ix_mfa_sessions_user_id", "mfa_sessions", ["user_id"])
        op.create_index("ix_mfa_sessions_id", "mfa_sessions", ["id"])


def downgrade() -> None:
    op.drop_index("ix_mfa_sessions_id", table_name="mfa_sessions")
    op.drop_index("ix_mfa_sessions_user_id", table_name="mfa_sessions")
    op.drop_table("mfa_sessions")

    op.drop_index("ix_session_tokens_id", table_name="session_tokens")
    op.drop_index("ix_session_tokens_refresh_token_hash", table_name="session_tokens")
    op.drop_index("ix_session_tokens_user_id", table_name="session_tokens")
    op.drop_table("session_tokens")

    op.drop_column("users", "google_account_email")
    op.drop_column("users", "google_access_token_expires_at")
    op.drop_column("users", "google_access_token")
    op.drop_column("users", "google_refresh_token")
    op.drop_column("users", "mfa_temp_secret")
    op.drop_column("users", "mfa_secret")
    op.drop_column("users", "is_mfa_enabled")
