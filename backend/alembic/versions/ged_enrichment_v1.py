"""GED: workflows configurables, courrier enrichi, SLA, RDV (ODJ, tâches, statuts).

Revision ID: ged_enrichment_v1
Revises: qr_code_path_storage
"""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "ged_enrichment_v1"
down_revision = "qr_code_path_storage"
branch_labels = None
depends_on = None

_NS = uuid.UUID("8c5d0eb4-2a9b-5c1d-9e0f-aabbccddeeff")


def _uid(*parts: str) -> str:
    return str(uuid.uuid5(_NS, "/".join(parts)))


def upgrade() -> None:
    op.create_table(
        "workflow_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("subtype", sa.String(32), nullable=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_workflow_definitions_entity", "workflow_definitions", ["entity_type"])
    op.create_index("ix_workflow_definitions_subtype", "workflow_definitions", ["subtype"])

    op.create_table(
        "workflow_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "definition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_key", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_workflow_steps_def", "workflow_steps", ["definition_id"])
    op.create_index("ix_workflow_steps_key", "workflow_steps", ["step_key"])

    op.create_table(
        "workflow_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "definition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "from_step_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_steps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "to_step_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_steps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_key", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("requires_assignee", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_wf_trans_action", "workflow_transitions", ["action_key"])

    op.create_table(
        "workflow_transition_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "transition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_transitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("permission_key", sa.String(128), nullable=False),
    )

    op.create_table(
        "sla_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("qualification", sa.String(64), nullable=True),
        sa.Column("priority", sa.String(32), nullable=True),
        sa.Column("hours_allowed", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_sla_rules_entity", "sla_rules", ["entity_type"])

    op.create_table(
        "appointment_agenda_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_agenda_appt", "appointment_agenda_items", ["appointment_id"])

    op.create_table(
        "appointment_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
    )
    op.create_index("ix_appt_tasks_appt", "appointment_tasks", ["appointment_id"])

    # --- Convert mail / appointment status columns to VARCHAR (drop PG enums) ---
    conn = op.get_bind()
    conn.execute(sa.text("ALTER TABLE mail_documents ALTER COLUMN status TYPE VARCHAR(32) USING status::text"))
    conn.execute(
        sa.text("UPDATE mail_documents SET status = 'in_treatment' WHERE status = 'in_review'")
    )
    conn.execute(sa.text("ALTER TABLE workflow_states ALTER COLUMN status TYPE VARCHAR(32) USING status::text"))
    conn.execute(
        sa.text("UPDATE workflow_states SET status = 'in_treatment' WHERE status = 'in_review'")
    )
    conn.execute(sa.text("ALTER TABLE workflow_history ALTER COLUMN from_status TYPE VARCHAR(32) USING from_status::text"))
    conn.execute(sa.text("ALTER TABLE workflow_history ALTER COLUMN to_status TYPE VARCHAR(32) USING to_status::text"))
    conn.execute(
        sa.text("UPDATE workflow_history SET from_status = 'in_treatment' WHERE from_status = 'in_review'")
    )
    conn.execute(
        sa.text("UPDATE workflow_history SET to_status = 'in_treatment' WHERE to_status = 'in_review'")
    )
    conn.execute(sa.text("DROP TYPE IF EXISTS mailstatus CASCADE"))

    conn.execute(sa.text("ALTER TABLE appointments ALTER COLUMN status TYPE VARCHAR(32) USING status::text"))
    conn.execute(sa.text("DROP TYPE IF EXISTS appointmentstatus CASCADE"))

    # --- Mail columns ---
    op.add_column("mail_documents", sa.Column("direction", sa.String(16), nullable=False, server_default="inbound"))
    op.add_column("mail_documents", sa.Column("channel", sa.String(16), nullable=True))
    op.add_column("mail_documents", sa.Column("sender_name", sa.String(255), nullable=True))
    op.add_column("mail_documents", sa.Column("sender_email", sa.String(255), nullable=True))
    op.add_column("mail_documents", sa.Column("sender_phone", sa.String(64), nullable=True))
    op.add_column("mail_documents", sa.Column("qualification", sa.String(32), nullable=True))
    op.add_column(
        "mail_documents",
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=True),
    )
    op.add_column("mail_documents", sa.Column("intended_send_channel", sa.String(64), nullable=True))
    op.add_column("mail_documents", sa.Column("sent_at", sa.DateTime(), nullable=True))
    op.add_column("mail_documents", sa.Column("outbound_send_status", sa.String(32), nullable=True))
    op.add_column(
        "mail_documents",
        sa.Column(
            "workflow_definition_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_definitions.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_mail_documents_direction", "mail_documents", ["direction"])
    op.create_index("ix_mail_documents_qualification", "mail_documents", ["qualification"])

    # --- Appointment columns ---
    op.add_column("appointments", sa.Column("proposed_start_time", sa.DateTime(), nullable=True))
    op.add_column("appointments", sa.Column("proposed_end_time", sa.DateTime(), nullable=True))
    op.add_column("appointments", sa.Column("hierarchy_validated_at", sa.DateTime(), nullable=True))
    op.add_column(
        "appointments",
        sa.Column("hierarchy_validated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column("appointments", sa.Column("minutes_text", sa.Text(), nullable=True))
    op.add_column("appointments", sa.Column("minutes_at", sa.DateTime(), nullable=True))
    op.add_column(
        "appointments",
        sa.Column("minutes_author_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    _seed_workflows_and_sla(conn)


def _seed_workflows_and_sla(conn) -> None:
    now = datetime.utcnow()
    wf_ib = _uid("wf", "inbound")
    wf_ob = _uid("wf", "outbound")
    wf_int = _uid("wf", "internal")

    conn.execute(
        sa.text(
            """
            INSERT INTO workflow_definitions (id, entity_type, subtype, name, version, is_active, created_at)
            VALUES (:id, 'mail', 'inbound', 'Courrier entrant', 1, true, :ts)
            """
        ),
        {"id": wf_ib, "ts": now},
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO workflow_definitions (id, entity_type, subtype, name, version, is_active, created_at)
            VALUES (:id, 'mail', 'outbound', 'Courrier sortant', 1, true, :ts)
            """
        ),
        {"id": wf_ob, "ts": now},
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO workflow_definitions (id, entity_type, subtype, name, version, is_active, created_at)
            VALUES (:id, 'mail', 'internal', 'Courrier interne', 1, true, :ts)
            """
        ),
        {"id": wf_int, "ts": now},
    )

    def steps_for(def_id: str, keys: list[tuple[str, str, int]]) -> dict[str, str]:
        out = {}
        for key, label, order in keys:
            sid = _uid("step", def_id, key)
            out[key] = sid
            conn.execute(
                sa.text(
                    """
                    INSERT INTO workflow_steps (id, definition_id, step_key, label, sort_order)
                    VALUES (:id, :def_id, :k, :lab, :ord)
                    """
                ),
                {"id": sid, "def_id": def_id, "k": key, "lab": label, "ord": order},
            )
        return out

    def add_tr(
        def_id: str,
        fid: str,
        tid: str,
        action: str,
        label: str,
        perm: str,
        req_a: bool = False,
    ) -> None:
        trid = _uid("tr", def_id, action, fid, tid)
        conn.execute(
            sa.text(
                """
                INSERT INTO workflow_transitions
                (id, definition_id, from_step_id, to_step_id, action_key, label, requires_assignee)
                VALUES (:id, :def_id, :fid, :tid, :ak, :lab, :ra)
                """
            ),
            {
                "id": trid,
                "def_id": def_id,
                "fid": fid,
                "tid": tid,
                "ak": action,
                "lab": label,
                "ra": req_a,
            },
        )
        pid = _uid("perm", trid)
        conn.execute(
            sa.text(
                """
                INSERT INTO workflow_transition_permissions (id, transition_id, permission_key)
                VALUES (:id, :tid, :pk)
                """
            ),
            {"id": pid, "tid": trid, "pk": perm},
        )

    ib = steps_for(
        wf_ib,
        [
            ("received", "Réception", 0),
            ("indexed", "Indexé", 1),
            ("assigned", "Affecté", 2),
            ("in_treatment", "En traitement", 3),
            ("pending_validation", "En validation", 4),
            ("on_hold", "En attente", 5),
            ("approved", "Approuvé", 6),
            ("rejected", "Rejeté", 7),
            ("archived", "Archivé", 8),
        ],
    )
    add_tr(wf_ib, ib["received"], ib["indexed"], "index_document", "Indexer", "mail.workflow.index")
    add_tr(wf_ib, ib["indexed"], ib["assigned"], "assign", "Affecter", "mail.workflow.assign", True)
    add_tr(wf_ib, ib["assigned"], ib["in_treatment"], "start_treatment", "Traitement", "mail.workflow.treat")
    add_tr(wf_ib, ib["in_treatment"], ib["pending_validation"], "submit_validation", "Soumettre validation", "mail.workflow.submit_validation")
    add_tr(wf_ib, ib["in_treatment"], ib["on_hold"], "hold", "Mettre en attente", "mail.workflow.hold")
    add_tr(wf_ib, ib["on_hold"], ib["in_treatment"], "resume", "Reprendre", "mail.workflow.resume")
    add_tr(wf_ib, ib["pending_validation"], ib["approved"], "approve", "Approuver", "mail.workflow.approve")
    add_tr(wf_ib, ib["pending_validation"], ib["rejected"], "reject", "Rejeter", "mail.workflow.reject")
    add_tr(wf_ib, ib["pending_validation"], ib["in_treatment"], "request_changes", "Demander compléments", "mail.workflow.request_changes")
    add_tr(wf_ib, ib["approved"], ib["archived"], "archive", "Archiver", "mail.workflow.archive")
    add_tr(wf_ib, ib["rejected"], ib["archived"], "archive", "Archiver", "mail.workflow.archive")

    ob = steps_for(
        wf_ob,
        [
            ("received", "Brouillon / réception", 0),
            ("in_treatment", "Rédaction", 1),
            ("pending_validation", "Validation interne", 2),
            ("approved", "Validé envoi", 3),
            ("archived", "Archivé", 4),
        ],
    )
    add_tr(wf_ob, ob["received"], ob["in_treatment"], "start_treatment", "Traitement", "mail.workflow.treat")
    add_tr(wf_ob, ob["in_treatment"], ob["pending_validation"], "submit_validation", "Soumettre validation", "mail.workflow.submit_validation")
    add_tr(wf_ob, ob["pending_validation"], ob["approved"], "approve", "Approuver", "mail.workflow.approve")
    add_tr(wf_ob, ob["approved"], ob["archived"], "archive", "Archiver", "mail.workflow.archive")

    inn = steps_for(
        wf_int,
        [
            ("received", "Création", 0),
            ("assigned", "Affecté", 1),
            ("in_treatment", "Traitement", 2),
            ("approved", "Validé", 3),
            ("archived", "Archivé", 4),
        ],
    )
    add_tr(wf_int, inn["received"], inn["assigned"], "assign", "Affecter", "mail.workflow.assign", True)
    add_tr(wf_int, inn["assigned"], inn["in_treatment"], "start_treatment", "Traitement", "mail.workflow.treat")
    add_tr(wf_int, inn["in_treatment"], inn["approved"], "approve", "Valider", "mail.workflow.approve")
    add_tr(wf_int, inn["approved"], inn["archived"], "archive", "Archiver", "mail.workflow.archive")

    sla_id = _uid("sla", "default")
    conn.execute(
        sa.text(
            """
            INSERT INTO sla_rules (id, entity_type, qualification, priority, hours_allowed, active, created_at)
            VALUES (:id, 'mail', NULL, NULL, 120, true, :ts)
            """
        ),
        {"id": sla_id, "ts": now},
    )


def downgrade() -> None:
    op.drop_index("ix_appt_tasks_appt", table_name="appointment_tasks")
    op.drop_table("appointment_tasks")
    op.drop_index("ix_agenda_appt", table_name="appointment_agenda_items")
    op.drop_table("appointment_agenda_items")

    op.drop_column("appointments", "minutes_author_id")
    op.drop_column("appointments", "minutes_at")
    op.drop_column("appointments", "minutes_text")
    op.drop_column("appointments", "hierarchy_validated_by_id")
    op.drop_column("appointments", "hierarchy_validated_at")
    op.drop_column("appointments", "proposed_end_time")
    op.drop_column("appointments", "proposed_start_time")

    op.drop_index("ix_mail_documents_qualification", table_name="mail_documents")
    op.drop_index("ix_mail_documents_direction", table_name="mail_documents")
    op.drop_column("mail_documents", "workflow_definition_id")
    op.drop_column("mail_documents", "outbound_send_status")
    op.drop_column("mail_documents", "sent_at")
    op.drop_column("mail_documents", "intended_send_channel")
    op.drop_column("mail_documents", "tags")
    op.drop_column("mail_documents", "qualification")
    op.drop_column("mail_documents", "sender_phone")
    op.drop_column("mail_documents", "sender_email")
    op.drop_column("mail_documents", "sender_name")
    op.drop_column("mail_documents", "channel")
    op.drop_column("mail_documents", "direction")

    op.drop_index("ix_sla_rules_entity", table_name="sla_rules")
    op.drop_table("sla_rules")

    op.drop_table("workflow_transition_permissions")
    op.drop_index("ix_wf_trans_action", table_name="workflow_transitions")
    op.drop_table("workflow_transitions")
    op.drop_index("ix_workflow_steps_key", table_name="workflow_steps")
    op.drop_index("ix_workflow_steps_def", table_name="workflow_steps")
    op.drop_table("workflow_steps")
    op.drop_index("ix_workflow_definitions_subtype", table_name="workflow_definitions")
    op.drop_index("ix_workflow_definitions_entity", table_name="workflow_definitions")
    op.drop_table("workflow_definitions")
