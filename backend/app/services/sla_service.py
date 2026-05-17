"""Application des règles SLA aux courriers (échéance de réponse)."""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.mail import MailDocument
from app.models.sla_rule import SlaRule


def _rule_score(rule: SlaRule, qualification: Optional[str], priority: str) -> Optional[int]:
    """Score plus élevé = plus spécifique. None si la règle ne s'applique pas."""
    sc = 0
    if rule.qualification:
        if qualification != rule.qualification:
            return None
        sc += 2
    if rule.priority:
        if priority != rule.priority:
            return None
        sc += 1
    return sc


def pick_mail_sla_rule(
    db: Session,
    qualification: Optional[str],
    priority: str,
) -> Optional[SlaRule]:
    rules = (
        db.query(SlaRule)
        .filter(SlaRule.entity_type == "mail", SlaRule.active.is_(True))
        .all()
    )
    best: Optional[SlaRule] = None
    best_sc = -1
    for r in rules:
        sc = _rule_score(r, qualification, priority)
        if sc is None:
            continue
        if sc > best_sc:
            best_sc = sc
            best = r
    return best


def apply_response_deadline_from_sla(db: Session, document: MailDocument) -> None:
    qual = document.qualification.value if document.qualification else None
    rule = pick_mail_sla_rule(db, qual, document.priority or "normal")
    if not rule:
        return
    document.response_deadline = datetime.utcnow() + timedelta(hours=rule.hours_allowed)
