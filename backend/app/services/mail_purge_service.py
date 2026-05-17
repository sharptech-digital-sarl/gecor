import uuid

from sqlalchemy.orm import Session, joinedload

from app.models.mail import MailDocument, WorkflowHistory, WorkflowState
from app.models.notification import Notification
from app.services.storage_service import storage_service


def purge_mail_document(db: Session, document_id: uuid.UUID) -> bool:
    """Supprime un courrier et ses fichiers associés. Retourne False si introuvable."""
    doc = (
        db.query(MailDocument)
        .options(joinedload(MailDocument.versions), joinedload(MailDocument.signatures))
        .filter(MailDocument.id == document_id)
        .first()
    )
    if not doc:
        return False

    for sig in list(doc.signatures or []):
        try:
            storage_service.delete_file(sig.signature_image_path)
        except Exception:
            pass
        db.delete(sig)

    for ver in list(doc.versions or []):
        try:
            storage_service.delete_file(ver.file_path)
        except Exception:
            pass
        db.delete(ver)

    db.query(WorkflowHistory).filter(WorkflowHistory.document_id == doc.id).delete(
        synchronize_session=False
    )
    db.query(WorkflowState).filter(WorkflowState.document_id == doc.id).delete(
        synchronize_session=False
    )

    db.query(Notification).filter(Notification.related_document_id == doc.id).delete(
        synchronize_session=False
    )

    try:
        storage_service.delete_file(doc.file_path)
    except Exception:
        pass

    db.delete(doc)
    db.flush()
    return True
