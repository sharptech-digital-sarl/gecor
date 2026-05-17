"""Courrier entrant : étape pending_director + transitions (avis direction avant DG).

Revision ID: mail_wf_pending_dir
Revises: pending_pwd_hash_ch
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "mail_wf_pending_dir"
down_revision = "pending_pwd_hash_ch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    wf = conn.execute(
        sa.text(
            "SELECT id FROM workflow_definitions WHERE entity_type = 'mail' "
            "AND subtype = 'inbound' AND is_active = true LIMIT 1"
        )
    ).fetchone()
    if not wf:
        return
    wf_id = wf[0]

    exists = conn.execute(
        sa.text(
            "SELECT 1 FROM workflow_steps WHERE definition_id = :d AND step_key = 'pending_director' LIMIT 1"
        ),
        {"d": wf_id},
    ).fetchone()
    if exists:
        return

    conn.execute(
        sa.text(
            "UPDATE workflow_steps SET sort_order = sort_order + 1 "
            "WHERE definition_id = :d AND sort_order >= 4"
        ),
        {"d": wf_id},
    )

    step_pd = str(uuid.uuid4())
    conn.execute(
        sa.text(
            """
            INSERT INTO workflow_steps (id, definition_id, step_key, label, sort_order)
            VALUES (:id, :d, 'pending_director', 'En validation direction', 4)
            """
        ),
        {"id": step_pd, "d": wf_id},
    )

    def sid(key: str) -> str | None:
        r = conn.execute(
            sa.text(
                "SELECT id FROM workflow_steps WHERE definition_id = :d AND step_key = :k LIMIT 1"
            ),
            {"d": wf_id, "k": key},
        ).scalar()
        return str(r) if r else None

    s_in_t = sid("in_treatment")
    s_pd = step_pd
    s_pv = sid("pending_validation")
    s_rej = sid("rejected")

    if not all([s_in_t, s_pv, s_rej]):
        return

    def del_tr(action: str, fk: str, tk: str) -> None:
        conn.execute(
            sa.text(
                """
                DELETE FROM workflow_transition_permissions WHERE transition_id IN (
                  SELECT wt.id FROM workflow_transitions wt
                  JOIN workflow_steps fs ON wt.from_step_id = fs.id
                  JOIN workflow_steps ts ON wt.to_step_id = ts.id
                  WHERE wt.definition_id = :d AND wt.action_key = :a
                    AND fs.step_key = :fk AND ts.step_key = :tk
                )
                """
            ),
            {"d": wf_id, "a": action, "fk": fk, "tk": tk},
        )
        conn.execute(
            sa.text(
                """
                DELETE FROM workflow_transitions WHERE id IN (
                  SELECT wt.id FROM workflow_transitions wt
                  JOIN workflow_steps fs ON wt.from_step_id = fs.id
                  JOIN workflow_steps ts ON wt.to_step_id = ts.id
                  WHERE wt.definition_id = :d AND wt.action_key = :a
                    AND fs.step_key = :fk AND ts.step_key = :tk
                )
                """
            ),
            {"d": wf_id, "a": action, "fk": fk, "tk": tk},
        )

    del_tr("submit_validation", "in_treatment", "pending_validation")

    def add_tr(action: str, label: str, perm: str, fid: str, tid: str, req_a: bool = False) -> None:
        trid = str(uuid.uuid4())
        conn.execute(
            sa.text(
                """
                INSERT INTO workflow_transitions
                (id, definition_id, from_step_id, to_step_id, action_key, label, requires_assignee)
                VALUES (:id, :d, :fid, :tid, :ak, :lab, :ra)
                """
            ),
            {
                "id": trid,
                "d": wf_id,
                "fid": fid,
                "tid": tid,
                "ak": action,
                "lab": label,
                "ra": req_a,
            },
        )
        pid = str(uuid.uuid4())
        conn.execute(
            sa.text(
                """
                INSERT INTO workflow_transition_permissions (id, transition_id, permission_key)
                VALUES (:id, :tid, :pk)
                """
            ),
            {"id": pid, "tid": trid, "pk": perm},
        )

    add_tr(
        "submit_to_director",
        "Transmettre à la direction",
        "mail.workflow.submit_to_director",
        s_in_t,
        s_pd,
    )
    add_tr(
        "director_forward_dg",
        "Transmettre au DG (avis final)",
        "mail.workflow.escalate_to_dg",
        s_pd,
        s_pv,
    )
    add_tr(
        "request_changes",
        "Demander compléments",
        "mail.workflow.request_changes",
        s_pd,
        s_in_t,
    )
    add_tr("reject", "Rejeter", "mail.workflow.reject", s_pd, s_rej)


def downgrade() -> None:
    conn = op.get_bind()
    wf = conn.execute(
        sa.text(
            "SELECT id FROM workflow_definitions WHERE entity_type = 'mail' "
            "AND subtype = 'inbound' AND is_active = true LIMIT 1"
        )
    ).fetchone()
    if not wf:
        return
    wf_id = wf[0]

    step_pd = conn.execute(
        sa.text(
            "SELECT id FROM workflow_steps WHERE definition_id = :d AND step_key = 'pending_director' LIMIT 1"
        ),
        {"d": wf_id},
    ).scalar()
    if not step_pd:
        return

    conn.execute(
        sa.text(
            "DELETE FROM workflow_transition_permissions WHERE transition_id IN ("
            "SELECT id FROM workflow_transitions WHERE definition_id = :d "
            "AND (from_step_id = :s OR to_step_id = :s))"
        ),
        {"d": wf_id, "s": step_pd},
    )
    conn.execute(
        sa.text(
            "DELETE FROM workflow_transitions WHERE definition_id = :d "
            "AND (from_step_id = :s OR to_step_id = :s)"
        ),
        {"d": wf_id, "s": step_pd},
    )
    conn.execute(sa.text("DELETE FROM workflow_steps WHERE id = :s"), {"s": step_pd})

    conn.execute(
        sa.text(
            "UPDATE workflow_steps SET sort_order = sort_order - 1 "
            "WHERE definition_id = :d AND sort_order >= 5"
        ),
        {"d": wf_id},
    )

    s_in_t = conn.execute(
        sa.text("SELECT id FROM workflow_steps WHERE definition_id = :d AND step_key = 'in_treatment'"),
        {"d": wf_id},
    ).scalar()
    s_pv = conn.execute(
        sa.text("SELECT id FROM workflow_steps WHERE definition_id = :d AND step_key = 'pending_validation'"),
        {"d": wf_id},
    ).scalar()
    if s_in_t and s_pv:
        trid = str(uuid.uuid4())
        pid = str(uuid.uuid4())
        conn.execute(
            sa.text(
                """
                INSERT INTO workflow_transitions
                (id, definition_id, from_step_id, to_step_id, action_key, label, requires_assignee)
                VALUES (:id, :d, :fid, :tid, 'submit_validation', 'Soumettre validation', false)
                """
            ),
            {"id": trid, "d": wf_id, "fid": s_in_t, "tid": s_pv},
        )
        conn.execute(
            sa.text(
                "INSERT INTO workflow_transition_permissions (id, transition_id, permission_key) VALUES (:id, :tid, 'mail.workflow.submit_validation')"
            ),
            {"id": pid, "tid": trid},
        )
