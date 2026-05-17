from datetime import datetime
from typing import Optional
import logging
import uuid

logger = logging.getLogger(__name__)


class AuditLogger:
    """Audit logging: structured logs + persistence in audit_events (separate DB session)."""

    def _persist(
        self,
        action: str,
        user_id: Optional[uuid.UUID],
        resource_type: str,
        resource_id: Optional[uuid.UUID] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        try:
            from app.core.database import SessionLocal
            from app.models.audit_event import AuditEvent

            row = AuditEvent(
                actor_user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details or None,
                ip_address=ip_address,
                user_agent=(user_agent[:512] if user_agent else None),
            )
            with SessionLocal() as session:
                session.add(row)
                session.commit()
        except Exception as e:
            logger.warning("AUDIT DB write failed: %s", e, exc_info=False)

    def log_action(
        self,
        action: str,
        user_id: Optional[uuid.UUID],
        resource_type: str,
        resource_id: Optional[uuid.UUID] = None,
        details: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        persist_db: bool = True,
    ):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
        }

        logger.info(f"AUDIT: {log_entry}")

        if persist_db:
            self._persist(
                action=action,
                user_id=user_id,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                ip_address=ip_address,
                user_agent=user_agent,
            )

        return log_entry

    def log_login(
        self,
        user_id: Optional[uuid.UUID],
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        persist_db: bool = True,
    ):
        return self.log_action(
            action="login_attempt",
            user_id=user_id if success else None,
            resource_type="authentication",
            details={"success": success},
            ip_address=ip_address,
            user_agent=user_agent,
            persist_db=persist_db,
        )

    def log_document_access(
        self,
        user_id: uuid.UUID,
        document_id: uuid.UUID,
        action: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        persist_db: bool = True,
    ):
        return self.log_action(
            action=action,
            user_id=user_id,
            resource_type="document",
            resource_id=document_id,
            ip_address=ip_address,
            user_agent=user_agent,
            persist_db=persist_db,
        )

    def log_appointment_change(
        self,
        user_id: uuid.UUID,
        appointment_id: uuid.UUID,
        action: str,
        changes: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        persist_db: bool = True,
    ):
        return self.log_action(
            action=action,
            user_id=user_id,
            resource_type="appointment",
            resource_id=appointment_id,
            details={"changes": changes},
            ip_address=ip_address,
            user_agent=user_agent,
            persist_db=persist_db,
        )


audit_logger = AuditLogger()
