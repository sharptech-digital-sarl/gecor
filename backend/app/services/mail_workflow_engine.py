"""Moteur de workflow courrier : transitions en base + repli matrice code."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy.orm import Session, joinedload

from app.models.mail import MailDirection, MailDocument, MailStatus, _coerce_mail_status
from app.models.user import User
from app.models.workflow_config import WorkflowDefinition, WorkflowTransition


@dataclass
class TransitionInfo:
    action_key: str
    to_status: MailStatus
    label: Optional[str]
    requires_assignee: bool
    permission_keys: List[str]


# Repli si aucune définition active en base (même logique que le seed Alembic)
# Courrier entrant : Reçu → Enregistré → Affecté → En traitement → … → Validé → Clôturé → Archivé
_FALLBACK: Dict[str, List[Tuple[str, MailStatus, str, bool, List[str]]]] = {
    MailDirection.INBOUND.value: [
        ("index_document", MailStatus.INDEXED, "Enregistrer / indexer", False, ["mail.workflow.index", "mail.workflow.all"]),
        ("assign", MailStatus.ASSIGNED, "Affecter au service (orientation)", True, ["mail.workflow.assign", "mail.workflow.all"]),
        ("start_treatment", MailStatus.IN_TREATMENT, "Mettre en traitement", False, ["mail.workflow.treat", "mail.workflow.all"]),
        (
            "submit_to_director",
            MailStatus.PENDING_DIRECTOR,
            "Transmettre à la direction (avis)",
            False,
            ["mail.workflow.submit_to_director", "mail.workflow.all"],
        ),
        (
            "director_forward_dg",
            MailStatus.PENDING_VALIDATION,
            "Transmettre au DG (avis final)",
            False,
            ["mail.workflow.escalate_to_dg", "mail.workflow.all"],
        ),
        ("hold", MailStatus.ON_HOLD, "Mettre en attente", False, ["mail.workflow.hold", "mail.workflow.all"]),
        ("resume", MailStatus.IN_TREATMENT, "Reprendre le traitement", False, ["mail.workflow.resume", "mail.workflow.all"]),
        ("approve", MailStatus.APPROVED, "Valider (DG)", False, ["mail.workflow.approve", "mail.workflow.all"]),
        ("reject", MailStatus.REJECTED, "Rejeter", False, ["mail.workflow.reject", "mail.workflow.all"]),
        ("request_changes", MailStatus.IN_TREATMENT, "Demander des compléments", False, ["mail.workflow.request_changes", "mail.workflow.all"]),
        ("close", MailStatus.CLOSED, "Clôturer", False, ["mail.workflow.close", "mail.workflow.all"]),
        ("archive", MailStatus.ARCHIVED, "Archiver", False, ["mail.workflow.archive", "mail.workflow.all"]),
        ("restore", MailStatus.CLOSED, "Restaurer depuis les archives", False, ["mail.workflow.restore", "mail.workflow.all"]),
    ],
    MailDirection.OUTBOUND.value: [
        ("start_treatment", MailStatus.IN_TREATMENT, "Rédaction / traitement", False, ["mail.workflow.treat", "mail.workflow.all"]),
        ("submit_validation", MailStatus.PENDING_VALIDATION, "Soumettre validation interne", False, ["mail.workflow.submit_validation", "mail.workflow.all"]),
        ("approve", MailStatus.APPROVED, "Valider (prêt envoi)", False, ["mail.workflow.approve", "mail.workflow.all"]),
        ("archive", MailStatus.ARCHIVED, "Enregistrer / archiver après envoi", False, ["mail.workflow.archive", "mail.workflow.all"]),
    ],
    MailDirection.INTERNAL.value: [
        ("assign", MailStatus.ASSIGNED, "Affecter", True, ["mail.workflow.assign", "mail.workflow.all"]),
        ("start_treatment", MailStatus.IN_TREATMENT, "Traitement", False, ["mail.workflow.treat", "mail.workflow.all"]),
        ("approve", MailStatus.APPROVED, "Clôturer validation", False, ["mail.workflow.approve", "mail.workflow.all"]),
        ("archive", MailStatus.ARCHIVED, "Archiver", False, ["mail.workflow.archive", "mail.workflow.all"]),
    ],
}

# (from_status, action_key) -> to_status pour repli
_FALLBACK_EDGES: Dict[str, Dict[Tuple[str, str], MailStatus]] = {}


def _build_fallback_edges() -> Dict[str, Dict[Tuple[str, str], MailStatus]]:
    out: Dict[str, Dict[Tuple[str, str], MailStatus]] = {
        MailDirection.INBOUND.value: {
            (MailStatus.RECEIVED.value, "index_document"): MailStatus.INDEXED,
            (MailStatus.INDEXED.value, "assign"): MailStatus.ASSIGNED,
            (MailStatus.ASSIGNED.value, "start_treatment"): MailStatus.IN_TREATMENT,
            (MailStatus.IN_TREATMENT.value, "submit_to_director"): MailStatus.PENDING_DIRECTOR,
            (MailStatus.PENDING_DIRECTOR.value, "director_forward_dg"): MailStatus.PENDING_VALIDATION,
            (MailStatus.PENDING_DIRECTOR.value, "request_changes"): MailStatus.IN_TREATMENT,
            (MailStatus.PENDING_DIRECTOR.value, "reject"): MailStatus.REJECTED,
            (MailStatus.IN_TREATMENT.value, "hold"): MailStatus.ON_HOLD,
            (MailStatus.ON_HOLD.value, "resume"): MailStatus.IN_TREATMENT,
            (MailStatus.PENDING_VALIDATION.value, "approve"): MailStatus.APPROVED,
            (MailStatus.PENDING_VALIDATION.value, "reject"): MailStatus.REJECTED,
            (MailStatus.PENDING_VALIDATION.value, "request_changes"): MailStatus.IN_TREATMENT,
            (MailStatus.APPROVED.value, "close"): MailStatus.CLOSED,
            (MailStatus.CLOSED.value, "archive"): MailStatus.ARCHIVED,
            (MailStatus.REJECTED.value, "archive"): MailStatus.ARCHIVED,
            (MailStatus.ARCHIVED.value, "restore"): MailStatus.CLOSED,
        },
        MailDirection.OUTBOUND.value: {
            (MailStatus.RECEIVED.value, "start_treatment"): MailStatus.IN_TREATMENT,
            (MailStatus.IN_TREATMENT.value, "submit_validation"): MailStatus.PENDING_VALIDATION,
            (MailStatus.PENDING_VALIDATION.value, "approve"): MailStatus.APPROVED,
            (MailStatus.APPROVED.value, "archive"): MailStatus.ARCHIVED,
        },
        MailDirection.INTERNAL.value: {
            (MailStatus.RECEIVED.value, "assign"): MailStatus.ASSIGNED,
            (MailStatus.ASSIGNED.value, "start_treatment"): MailStatus.IN_TREATMENT,
            (MailStatus.IN_TREATMENT.value, "approve"): MailStatus.APPROVED,
            (MailStatus.APPROVED.value, "archive"): MailStatus.ARCHIVED,
        },
    }
    return out


_FALLBACK_EDGES = _build_fallback_edges()


def _user_may(user: User, permission_keys: List[str]) -> bool:
    from app.core.effective_permissions import get_effective_permissions

    if user.has_role("master"):
        return True
    eff = get_effective_permissions(user)
    if "mail.workflow.all" in eff:
        return True
    return any(pk in eff for pk in permission_keys)


class MailWorkflowEngine:
    def get_active_definition(
        self, db: Session, direction: MailDirection
    ) -> Optional[WorkflowDefinition]:
        return (
            db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.entity_type == "mail",
                WorkflowDefinition.subtype == direction.value,
                WorkflowDefinition.is_active.is_(True),
            )
            .first()
        )

    def _transitions_from_db(
        self, db: Session, document: MailDocument
    ) -> List[TransitionInfo]:
        dfn = self.get_active_definition(db, document.direction)
        if not dfn:
            return []
        q = (
            db.query(WorkflowTransition)
            .options(
                joinedload(WorkflowTransition.from_step),
                joinedload(WorkflowTransition.to_step),
                joinedload(WorkflowTransition.permissions),
            )
            .filter(WorkflowTransition.definition_id == dfn.id)
            .all()
        )
        cur = document.status.value if isinstance(document.status, MailStatus) else str(document.status)
        out: List[TransitionInfo] = []
        for t in q:
            fk = t.from_step.step_key
            if fk != cur:
                continue
            try:
                to_st = MailStatus(t.to_step.step_key)
            except ValueError:
                continue
            pkeys = [p.permission_key for p in t.permissions]
            if not pkeys:
                continue
            out.append(
                TransitionInfo(
                    action_key=t.action_key,
                    to_status=to_st,
                    label=t.label,
                    requires_assignee=t.requires_assignee,
                    permission_keys=pkeys,
                )
            )
        return out

    def _transitions_fallback(self, document: MailDocument) -> List[TransitionInfo]:
        cur = document.status.value if isinstance(document.status, MailStatus) else str(document.status)
        sub = _FALLBACK.get(document.direction.value, _FALLBACK[MailDirection.INBOUND.value])
        edges = _FALLBACK_EDGES.get(document.direction.value, {})
        out: List[TransitionInfo] = []
        for action_key, to_st, label, req_a, pkeys in sub:
            if edges.get((cur, action_key)) != to_st:
                continue
            out.append(
                TransitionInfo(
                    action_key=action_key,
                    to_status=to_st,
                    label=label,
                    requires_assignee=req_a,
                    permission_keys=pkeys,
                )
            )
        return out

    def list_available_transitions(
        self, db: Session, user: User, document: MailDocument
    ) -> List[Dict[str, Any]]:
        raw = self._transitions_from_db(db, document)
        if not raw:
            raw = self._transitions_fallback(document)
        seen = set()
        result: List[Dict[str, Any]] = []
        for t in raw:
            if not _user_may(user, t.permission_keys):
                continue
            key = (t.action_key, t.to_status.value)
            if key in seen:
                continue
            seen.add(key)
            result.append(
                {
                    "action_key": t.action_key,
                    "to_status": t.to_status.value,
                    "label": t.label or t.action_key,
                    "requires_assignee": t.requires_assignee,
                }
            )
        return result

    def apply_transition(
        self,
        db: Session,
        user: User,
        document: MailDocument,
        action_key: str,
        assigned_to_id: Optional[uuid.UUID] = None,
    ) -> Tuple[bool, str]:
        transitions = self._transitions_from_db(db, document)
        if not transitions:
            transitions = self._transitions_fallback(document)

        chosen = next((t for t in transitions if t.action_key == action_key), None)
        if not chosen:
            return False, "Transition non autorisée ou action inconnue"

        if not _user_may(user, chosen.permission_keys):
            return False, "Permission insuffisante pour cette action"

        if chosen.requires_assignee and not assigned_to_id:
            return False, "Un destinataire (assigned_to_id) est requis pour cette action"

        prev_status = _coerce_mail_status(document.status)
        document.status = chosen.to_status
        if assigned_to_id:
            document.assigned_to = assigned_to_id
        from datetime import datetime

        if chosen.to_status == MailStatus.ARCHIVED:
            document.archived_at = datetime.utcnow()
        elif prev_status == MailStatus.ARCHIVED:
            document.archived_at = None

        return True, ""


mail_workflow_engine = MailWorkflowEngine()
