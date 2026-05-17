"""appointments public fields, public posts, in-app notif, push subs, audit events

Revision ID: plan_audit_notify
Revises: add_google_event_id
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import UUID


revision = "plan_audit_notify"
down_revision = "add_google_event_id"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(name)


def _column_exists(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table(table):
        return False
    return col in [c["name"] for c in insp.get_columns(table)]


def upgrade() -> None:
    if not _column_exists("appointments", "booking_source"):
        op.add_column(
            "appointments",
            sa.Column("booking_source", sa.String(32), nullable=False, server_default="internal"),
        )
    if not _column_exists("appointments", "internal_notes"):
        op.add_column("appointments", sa.Column("internal_notes", sa.Text(), nullable=True))
    if not _column_exists("appointments", "reception_validated_at"):
        op.add_column("appointments", sa.Column("reception_validated_at", sa.DateTime(), nullable=True))
    if not _column_exists("appointments", "reception_validated_by_id"):
        op.add_column(
            "appointments",
            sa.Column("reception_validated_by_id", UUID(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            "fk_appointments_reception_validated_by",
            "appointments",
            "users",
            ["reception_validated_by_id"],
            ["id"],
        )
    if not _column_exists("appointments", "visitor_booking_email_sent_at"):
        op.add_column(
            "appointments",
            sa.Column("visitor_booking_email_sent_at", sa.DateTime(), nullable=True),
        )

    if not _table_exists("public_information_posts"):
        op.create_table(
            "public_information_posts",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        )

    if not _table_exists("in_app_notifications"):
        op.create_table(
            "in_app_notifications",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=True),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_in_app_notifications_user_id", "in_app_notifications", ["user_id"])
        op.create_index("ix_in_app_notifications_created_at", "in_app_notifications", ["created_at"])

    if not _table_exists("push_subscriptions"):
        op.create_table(
            "push_subscriptions",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("endpoint", sa.Text(), nullable=False),
            sa.Column("p256dh", sa.String(500), nullable=False),
            sa.Column("auth", sa.String(500), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])
        op.create_index("ix_push_subscriptions_endpoint", "push_subscriptions", ["endpoint"], unique=True)

    if not _table_exists("audit_events"):
        op.create_table(
            "audit_events",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("timestamp", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("actor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("action", sa.String(128), nullable=False),
            sa.Column("resource_type", sa.String(128), nullable=False),
            sa.Column("resource_id", UUID(as_uuid=True), nullable=True),
            sa.Column("details", sa.JSON(), nullable=True),
            sa.Column("ip_address", sa.String(64), nullable=True),
            sa.Column("user_agent", sa.String(512), nullable=True),
        )
        op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])
        op.create_index("ix_audit_events_actor", "audit_events", ["actor_user_id"])
        op.create_index("ix_audit_events_action", "audit_events", ["action"])


def downgrade() -> None:
    if _table_exists("audit_events"):
        op.drop_index("ix_audit_events_action", table_name="audit_events")
        op.drop_index("ix_audit_events_actor", table_name="audit_events")
        op.drop_index("ix_audit_events_timestamp", table_name="audit_events")
        op.drop_table("audit_events")
    if _table_exists("push_subscriptions"):
        op.drop_index("ix_push_subscriptions_endpoint", table_name="push_subscriptions")
        op.drop_index("ix_push_subscriptions_user_id", table_name="push_subscriptions")
        op.drop_table("push_subscriptions")
    if _table_exists("in_app_notifications"):
        op.drop_index("ix_in_app_notifications_created_at", table_name="in_app_notifications")
        op.drop_index("ix_in_app_notifications_user_id", table_name="in_app_notifications")
        op.drop_table("in_app_notifications")
    if _table_exists("public_information_posts"):
        op.drop_table("public_information_posts")
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("appointments"):
        fk_names = [fk["name"] for fk in insp.get_foreign_keys("appointments")]
        if "fk_appointments_reception_validated_by" in fk_names:
            op.drop_constraint("fk_appointments_reception_validated_by", "appointments", type_="foreignkey")
    for col in (
        "visitor_booking_email_sent_at",
        "reception_validated_by_id",
        "reception_validated_at",
        "internal_notes",
        "booking_source",
    ):
        if _column_exists("appointments", col):
            op.drop_column("appointments", col)
