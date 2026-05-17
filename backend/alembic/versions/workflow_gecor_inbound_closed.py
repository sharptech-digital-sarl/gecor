"""Workflow courrier entrant : état Clôturé (closed), archivage archiviste, rôle archivist.

Révision du flux : Reçu → … → Validé (approved) → Clôturé (closed) → Archivé (archived).
Restauration : archived → closed.

Revision ID: wf_gecor_closed
Revises: add_user_preferred_locale
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime

import sqlalchemy as sa
from alembic import op

from app.core.permissions import DEFAULT_ROLE_PERMISSIONS

revision = "wf_gecor_closed"
down_revision = "add_user_preferred_locale"
branch_labels = None
depends_on = None

_NS = uuid.UUID("8c5d0eb4-2a9b-5c1d-9e0f-aabbccddeeff")


def _uid(*parts: str) -> str:
    return str(uuid.uuid5(_NS, "/".join(parts)))


def upgrade() -> None:
    conn = op.get_bind()

    wf_ib = _uid("wf", "inbound")
    row = conn.execute(
        sa.text("SELECT id FROM workflow_definitions WHERE entity_type = 'mail' AND subtype = 'inbound' LIMIT 1")
    ).fetchone()
    if not row:
        return

    s_approved = _uid("step", wf_ib, "approved")
    s_archived = _uid("step", wf_ib, "archived")
    s_closed = _uid("step", wf_ib, "closed")

    tr_old = _uid("tr", wf_ib, "archive", s_approved, s_archived)

    conn.execute(
        sa.text("DELETE FROM workflow_transition_permissions WHERE transition_id = CAST(:tid AS uuid)"),
        {"tid": tr_old},
    )
    conn.execute(
        sa.text("DELETE FROM workflow_transitions WHERE id = CAST(:tid AS uuid)"),
        {"tid": tr_old},
    )

    conn.execute(
        sa.text(
            """
            UPDATE workflow_steps SET sort_order = sort_order + 1
            WHERE definition_id = CAST(:def AS uuid) AND sort_order >= 7
            """
        ),
        {"def": wf_ib},
    )

    now = datetime.utcnow()
    conn.execute(
        sa.text(
            """
            INSERT INTO workflow_steps (id, definition_id, step_key, label, sort_order)
            VALUES (CAST(:id AS uuid), CAST(:def AS uuid), 'closed', :lab, 7)
            """
        ),
        {"id": s_closed, "def": wf_ib, "lab": "Clôturé"},
    )

    labels = [
        ("received", "Reçu"),
        ("indexed", "Enregistré"),
        ("assigned", "Affecté"),
        ("in_treatment", "En traitement"),
        ("pending_validation", "En validation"),
        ("on_hold", "En attente"),
        ("approved", "Validé"),
        ("rejected", "Rejeté"),
        ("archived", "Archivé"),
    ]
    for key, lab in labels:
        conn.execute(
            sa.text(
                """
                UPDATE workflow_steps SET label = :lab
                WHERE definition_id = CAST(:def AS uuid) AND step_key = :sk
                """
            ),
            {"lab": lab, "def": wf_ib, "sk": key},
        )

    tr_close = _uid("tr", wf_ib, "close", s_approved, s_closed)
    tr_arch = _uid("tr", wf_ib, "archive", s_closed, s_archived)
    tr_rest = _uid("tr", wf_ib, "restore", s_archived, s_closed)

    conn.execute(
        sa.text(
            """
            INSERT INTO workflow_transitions
            (id, definition_id, from_step_id, to_step_id, action_key, label, requires_assignee)
            VALUES
            (CAST(:id1 AS uuid), CAST(:def AS uuid), CAST(:f1 AS uuid), CAST(:t1 AS uuid), 'close', 'Clôturer', false),
            (CAST(:id2 AS uuid), CAST(:def AS uuid), CAST(:f2 AS uuid), CAST(:t2 AS uuid), 'archive', 'Archiver', false),
            (CAST(:id3 AS uuid), CAST(:def AS uuid), CAST(:f3 AS uuid), CAST(:t3 AS uuid), 'restore', 'Restaurer', false)
            """
        ),
        {
            "def": wf_ib,
            "id1": tr_close,
            "f1": s_approved,
            "t1": s_closed,
            "id2": tr_arch,
            "f2": s_closed,
            "t2": s_archived,
            "id3": tr_rest,
            "f3": s_archived,
            "t3": s_closed,
        },
    )

    p1 = _uid("perm", tr_close)
    p2 = _uid("perm", tr_arch)
    p3 = _uid("perm", tr_rest)
    conn.execute(
        sa.text(
            """
            INSERT INTO workflow_transition_permissions (id, transition_id, permission_key) VALUES
            (CAST(:p1 AS uuid), CAST(:t1 AS uuid), 'mail.workflow.close'),
            (CAST(:p2 AS uuid), CAST(:t2 AS uuid), 'mail.workflow.archive'),
            (CAST(:p3 AS uuid), CAST(:t3 AS uuid), 'mail.workflow.restore')
            """
        ),
        {"p1": p1, "t1": tr_close, "p2": p2, "t2": tr_arch, "p3": p3, "t3": tr_rest},
    )

    exists = conn.execute(sa.text("SELECT 1 FROM roles WHERE lower(name) = 'archivist' LIMIT 1")).scalar()
    if not exists:
        j = json.dumps(DEFAULT_ROLE_PERMISSIONS["archivist"])
        conn.execute(
            sa.text(
                """
                INSERT INTO roles (id, name, description, permissions, created_at, updated_at)
                VALUES (gen_random_uuid(), 'archivist', :d, CAST(:j AS jsonb), :ts, :ts)
                """
            ),
            {
                "d": "Archiviste — archivage et restauration des courriers.",
                "j": j,
                "ts": now,
            },
        )

    for name, perms in DEFAULT_ROLE_PERMISSIONS.items():
        conn.execute(
            sa.text("UPDATE roles SET permissions = CAST(:j AS jsonb) WHERE lower(name) = lower(:n)"),
            {"j": json.dumps(perms), "n": name},
        )


def downgrade() -> None:
    pass
