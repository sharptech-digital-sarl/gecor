from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List
import uuid

from app.models.mail import MailDocument, MailStatus, WorkflowHistory, WorkflowState
from app.models.user import User
from app.core.audit import audit_logger
from app.services.mail_workflow_engine import mail_workflow_engine


class WorkflowService:
    """Workflow courrier : routage OCR, transitions GED, échéances."""

    ROUTING_RULES = {
        "projects": [
            "loan",
            "prêt",
            "financing",
            "financement",
            "project",
            "projet",
            "application",
            "demande",
        ],
        "analysis": ["analysis", "analyse", "report", "rapport", "study", "étude"],
        "dg": ["urgent", "urgente", "director", "directeur", "approval", "approbation"],
    }

    def auto_route_document(
        self,
        db: Session,
        document: MailDocument,
        keywords: List[str],
    ) -> Optional[str]:
        keywords_lower = [k.lower() for k in keywords]

        for department, department_keywords in self.ROUTING_RULES.items():
            if any(kw in keywords_lower for kw in department_keywords):
                document.current_department = department
                document.status = MailStatus.IN_TREATMENT
                db.commit()
                return department

        return None

    def change_status(
        self,
        db: Session,
        document: MailDocument,
        new_status: MailStatus,
        user: User,
        notes: Optional[str] = None,
        assigned_to: Optional[uuid.UUID] = None,
        action_label: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Changement de statut avec historique (usage interne / admin). Préférer apply_transition côté API."""
        old_status = document.status
        document.status = new_status

        if assigned_to:
            document.assigned_to = assigned_to

        history = WorkflowHistory(
            document_id=document.id,
            from_status=old_status,
            to_status=new_status,
            action=action_label or f"status_changed_to_{new_status.value}",
            performed_by=user.id,
            notes=notes,
        )
        db.add(history)

        state = WorkflowState(
            document_id=document.id,
            status=new_status,
            department=document.current_department,
            notes=notes,
        )
        db.add(state)

        db.commit()
        db.refresh(document)

        audit_logger.log_action(
            action="mail_workflow",
            user_id=user.id,
            resource_type="mail_document",
            resource_id=document.id,
            details={
                "from_status": old_status.value if old_status else None,
                "to_status": new_status.value,
                "action": action_label or "status_change",
                "notes": notes,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def apply_transition(
        self,
        db: Session,
        document: MailDocument,
        user: User,
        action_key: str,
        notes: Optional[str] = None,
        assigned_to_id: Optional[uuid.UUID] = None,
        current_department: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        old_status = document.status
        ok, err = mail_workflow_engine.apply_transition(
            db, user, document, action_key, assigned_to_id=assigned_to_id
        )
        if not ok:
            from fastapi import HTTPException

            raise HTTPException(status_code=400, detail=err)

        if current_department is not None:
            d = (current_department or "").strip()
            document.current_department = d if d else None

        history = WorkflowHistory(
            document_id=document.id,
            from_status=old_status,
            to_status=document.status,
            action=action_key,
            performed_by=user.id,
            notes=notes,
        )
        db.add(history)

        state = WorkflowState(
            document_id=document.id,
            status=document.status,
            department=document.current_department,
            notes=notes,
        )
        db.add(state)

        db.commit()
        db.refresh(document)

        audit_logger.log_action(
            action="mail_workflow",
            user_id=user.id,
            resource_type="mail_document",
            resource_id=document.id,
            details={
                "from_status": old_status.value if old_status else None,
                "to_status": document.status.value,
                "action": action_key,
                "notes": notes,
                "assigned_to": str(assigned_to_id) if assigned_to_id else None,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def assign_document(
        self,
        db: Session,
        document: MailDocument,
        assigned_to: User,
        assigned_by: User,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Affectation : applique la transition « assign » si disponible pour l'utilisateur, sinon historique seul."""
        av = mail_workflow_engine.list_available_transitions(db, assigned_by, document)
        if any(a["action_key"] == "assign" for a in av):
            self.apply_transition(
                db,
                document,
                assigned_by,
                "assign",
                notes=notes,
                assigned_to_id=assigned_to.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return

        document.assigned_to = assigned_to.id

        history = WorkflowHistory(
            document_id=document.id,
            from_status=document.status,
            to_status=document.status,
            action="assigned",
            performed_by=assigned_by.id,
            notes=notes or f"Assigned to {assigned_to.full_name}",
        )
        db.add(history)
        db.commit()

        audit_logger.log_action(
            action="mail_assigned",
            user_id=assigned_by.id,
            resource_type="mail_document",
            resource_id=document.id,
            details={"assigned_to": str(assigned_to.id), "notes": notes},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def get_workflow_history(
        self,
        db: Session,
        document_id: uuid.UUID,
    ) -> List[WorkflowHistory]:
        return (
            db.query(WorkflowHistory)
            .filter(WorkflowHistory.document_id == document_id)
            .order_by(WorkflowHistory.created_at)
            .all()
        )

    def check_deadlines(self, db: Session) -> List[MailDocument]:
        now = datetime.utcnow()
        overdue = (
            db.query(MailDocument)
            .filter(
                MailDocument.response_deadline.isnot(None),
                MailDocument.response_deadline < now,
                MailDocument.status != MailStatus.ARCHIVED,
                MailDocument.is_overdue.is_(False),
            )
            .all()
        )

        for document in overdue:
            document.is_overdue = True
        if overdue:
            db.commit()

        return overdue


workflow_service = WorkflowService()
