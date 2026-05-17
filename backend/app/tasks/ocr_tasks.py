from celery import Task
from sqlalchemy.orm import Session
import asyncio
import logging
import uuid
from datetime import datetime

from app.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.mail import MailDocument
from app.services.ocr_service import ocr_service
from app.services.storage_service import storage_service
from app.services.workflow_service import workflow_service

logger = logging.getLogger(__name__)


def run_process_ocr(document_id: uuid.UUID) -> dict:
    """Run OCR pipeline synchronously (used by Celery worker or API fallback when Redis is down)."""
    db: Session = SessionLocal()
    try:
        document = db.query(MailDocument).filter(MailDocument.id == document_id).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            file_content = loop.run_until_complete(storage_service.get_file(document.file_path))
        finally:
            loop.close()

        ocr_result = ocr_service.process_document(file_content, document.mime_type)

        document.ocr_text = ocr_result["text"]
        document.ocr_keywords = ocr_result["keywords"]
        document.ocr_processed = True
        document.ocr_processed_at = datetime.utcnow()

        if ocr_result["keywords"]:
            workflow_service.auto_route_document(
                db,
                document,
                ocr_result["keywords"],
            )

        db.commit()
        return {"status": "success", "document_id": document_id}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="process_ocr")
def process_ocr_task(self: Task, document_id: uuid.UUID):
    """Async task to process OCR for a document (requires Redis + Celery worker)."""
    try:
        return run_process_ocr(document_id)
    except Exception as e:
        raise self.retry(exc=e, countdown=60, max_retries=3)


def queue_or_run_ocr(document_id: uuid.UUID) -> None:
    """Enqueue Celery task; if broker (Redis) is unavailable, run OCR in-process."""
    try:
        process_ocr_task.delay(document_id)
    except Exception as e:
        logger.warning(
            "Celery/Redis unavailable (%s); running OCR in-process for document %s",
            e,
            document_id,
        )
        try:
            run_process_ocr(document_id)
        except Exception:
            logger.exception("In-process OCR failed for document %s", document_id)
