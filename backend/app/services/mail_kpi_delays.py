"""Agrégats de délais courrier à partir de l’historique workflow (PostgreSQL)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.mail import MailDocument, MailStatus, WorkflowHistory


def _round_hours(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _avg_hours_to_status(db: Session, target: MailStatus) -> tuple[Optional[float], int]:
    sq = (
        db.query(
            WorkflowHistory.document_id.label("doc_id"),
            func.min(WorkflowHistory.created_at).label("first_at"),
        )
        .filter(WorkflowHistory.to_status == target)
        .group_by(WorkflowHistory.document_id)
        .subquery()
    )
    row = (
        db.query(
            func.avg(
                func.extract("epoch", sq.c.first_at - MailDocument.created_at) / 3600.0
            ).label("avg_h"),
            func.count(MailDocument.id).label("n"),
        )
        .select_from(MailDocument)
        .join(sq, MailDocument.id == sq.c.doc_id)
        .one()
    )
    return row.avg_h, int(row.n or 0)


def _median_hours_to_status(db: Session, target: MailStatus) -> Optional[float]:
    st = target.value
    return db.execute(
        text(
            """
            SELECT percentile_cont(0.5) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (x.first_at - x.created_at)) / 3600.0
            )
            FROM (
                SELECT d.created_at AS created_at, MIN(h.created_at) AS first_at
                FROM mail_documents d
                INNER JOIN workflow_history h
                    ON h.document_id = d.id AND h.to_status = :st
                GROUP BY d.id, d.created_at
            ) x
            """
        ),
        {"st": st},
    ).scalar()


def compute_mail_delay_kpis(db: Session) -> Dict[str, Any]:
    """
    Délais en heures depuis la création du courrier jusqu’à la première transition
    vers ``approved`` ou ``archived`` (échantillon = courriers ayant atteint ce jalon au moins une fois).
    """
    avg_app, n_app = _avg_hours_to_status(db, MailStatus.APPROVED)
    med_app = _median_hours_to_status(db, MailStatus.APPROVED) if n_app else None

    avg_arc, n_arc = _avg_hours_to_status(db, MailStatus.ARCHIVED)
    med_arc = _median_hours_to_status(db, MailStatus.ARCHIVED) if n_arc else None

    return {
        "to_approved": {
            "avg_hours": _round_hours(avg_app),
            "median_hours": _round_hours(med_app),
            "sample_count": n_app,
        },
        "to_archived": {
            "avg_hours": _round_hours(avg_arc),
            "median_hours": _round_hours(med_arc),
            "sample_count": n_arc,
        },
    }
