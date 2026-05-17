import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session
from datetime import datetime
import uuid

from app.core.audit import audit_logger
from app.core.database import get_db
from app.core.effective_permissions import user_has_any_permission, user_has_permission
from app.core.request_ip import get_client_ip
from app.core.security import get_current_user
from app.models.deletion_request import DeletionRequest, STATUS_PENDING, TARGET_MAIL
from app.models.user import User
from app.models.mail import (
    MailChannel,
    MailDirection,
    MailDocument,
    MailQualification,
    MailStatus,
    WorkflowHistory,
    WorkflowState,
)
from app.schemas.mail import (
    MailAvailableActionOut,
    MailDocument as MailDocumentSchema,
    MailDocumentUpdate,
    MailTransitionRequest,
    WorkflowHistory,
)
from app.schemas.deletion_request import DeletionRequestCreateBody
from app.schemas.user import BulkDeleteIds
from app.services.event_notifications import emit_in_app, user_ids_for_deletion_reviewers
from app.services.mail_workflow_notifications import notify_after_mail_transition
from app.services.mail_workflow_engine import mail_workflow_engine
from app.services.sla_service import apply_response_deadline_from_sla
from app.services.storage_service import storage_service
from app.services.workflow_service import workflow_service
from app.tasks.ocr_tasks import queue_or_run_ocr
from app.core.list_highlights import mail_highlight_destined

router = APIRouter()


def _mail_full_access_roles(user: User) -> bool:
    """Vue liste / détail sur tout le courrier (hors filtre créateur / affecté)."""
    return user.has_any_role("master", "director", "receptionist", "secretary", "archivist")


def _can_access_document(user: User, document: MailDocument) -> bool:
    if _mail_full_access_roles(user):
        return True
    return document.assigned_to == user.id or document.created_by == user.id


def _pending_mail_deletion_ids(db: Session) -> set:
    rows = (
        db.query(DeletionRequest.target_id)
        .filter(
            DeletionRequest.target_type == TARGET_MAIL,
            DeletionRequest.status == STATUS_PENDING,
        )
        .all()
    )
    return {r[0] for r in rows}


def generate_reference_number() -> str:
    return f"FPI-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def _doc_out(document: MailDocument, pending: bool, current_user: Optional[User] = None) -> MailDocumentSchema:
    d = MailDocumentSchema.model_validate(document)
    extra: dict = {"has_pending_deletion_request": pending}
    if current_user is not None:
        extra["highlight_destined"] = mail_highlight_destined(document, current_user.id)
    return d.model_copy(update=extra)


@router.post("/upload", response_model=MailDocumentSchema)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    priority: str = Form("normal"),
    response_deadline: Optional[datetime] = Form(None),
    direction: str = Form("inbound"),
    channel: Optional[str] = Form(None),
    sender_name: Optional[str] = Form(None),
    sender_email: Optional[str] = Form(None),
    sender_phone: Optional[str] = Form(None),
    qualification: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_has_permission(current_user, "mail.create"):
        raise HTTPException(status_code=403, detail="Not enough permissions to create mail")
    allowed_types = [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/tiff",
    ]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not allowed. Allowed types: {', '.join(allowed_types)}",
        )

    try:
        dir_enum = MailDirection(direction)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid direction")

    ch_enum = None
    if channel:
        try:
            ch_enum = MailChannel(channel)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid channel")

    qual_enum = None
    if qualification:
        try:
            qual_enum = MailQualification(qualification)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid qualification")

    tags_list: List[str] = []
    if tags:
        try:
            parsed = json.loads(tags)
            if isinstance(parsed, list):
                tags_list = [str(x) for x in parsed]
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="tags must be a JSON array of strings")

    file_content = await file.read()
    file_size = len(file_content)
    ref_number = generate_reference_number()
    file_name = f"{ref_number}_{file.filename}"
    file_path = await storage_service.save_file(file_content, file_name, subdirectory="mail")

    wd = mail_workflow_engine.get_active_definition(db, dir_enum)

    document = MailDocument(
        reference_number=ref_number,
        title=title,
        description=description,
        file_path=file_path,
        file_name=file.filename,
        file_size=file_size,
        mime_type=file.content_type,
        priority=priority,
        response_deadline=response_deadline,
        created_by=current_user.id,
        status=MailStatus.RECEIVED,
        direction=dir_enum,
        channel=ch_enum,
        sender_name=sender_name,
        sender_email=sender_email,
        sender_phone=sender_phone,
        qualification=qual_enum,
        tags=tags_list,
        workflow_definition_id=wd.id if wd else None,
    )

    db.add(document)
    db.flush()
    if not response_deadline:
        apply_response_deadline_from_sla(db, document)
    db.commit()
    db.refresh(document)

    queue_or_run_ocr(document.id)

    pending = document.id in _pending_mail_deletion_ids(db)
    return _doc_out(document, pending, current_user)


@router.get("/", response_model=List[MailDocumentSchema])
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    status: Optional[MailStatus] = None,
    assigned_to: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(MailDocument)

    if status:
        query = query.filter(MailDocument.status == status)
    if assigned_to:
        query = query.filter(MailDocument.assigned_to == assigned_to)

    if not _mail_full_access_roles(current_user):
        query = query.filter(
            (MailDocument.assigned_to == current_user.id) | (MailDocument.created_by == current_user.id)
        )

    documents = query.order_by(MailDocument.created_at.desc()).offset(skip).limit(limit).all()
    pending = _pending_mail_deletion_ids(db)
    return [_doc_out(doc, doc.id in pending, current_user) for doc in documents]


@router.post("/bulk-delete")
async def bulk_delete_mail_documents(
    body: BulkDeleteIds,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Supprime plusieurs courriers (master, director ou rôle admin — pas les groupes personnalisés)."""
    if not current_user.has_any_role("master", "director", "admin"):
        raise HTTPException(status_code=403, detail="Only master and director can bulk-delete mail")
    if not user_has_permission(current_user, "mail.delete"):
        raise HTTPException(status_code=403, detail="Not enough permissions to delete mail")
    from app.services.mail_purge_service import purge_mail_document

    deleted: List[str] = []
    skipped: List[dict] = []
    for document_id in body.ids:
        document = db.query(MailDocument).filter(MailDocument.id == document_id).first()
        if not document:
            skipped.append({"id": str(document_id), "reason": "not_found"})
            continue
        if not _can_access_document(current_user, document):
            skipped.append({"id": str(document_id), "reason": "access_denied"})
            continue
        if not purge_mail_document(db, document_id):
            skipped.append({"id": str(document_id), "reason": "purge_failed"})
            continue
        deleted.append(str(document_id))
    db.commit()
    return {"deleted": deleted, "skipped": skipped, "deleted_count": len(deleted)}


@router.get("/{document_id}/available-actions", response_model=List[MailAvailableActionOut])
async def mail_available_actions(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(MailDocument).filter(MailDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not _can_access_document(current_user, document):
        raise HTTPException(status_code=403, detail="Access denied")
    actions = mail_workflow_engine.list_available_transitions(db, current_user, document)
    return [MailAvailableActionOut(**a) for a in actions]


@router.post("/{document_id}/transition", response_model=MailDocumentSchema)
async def mail_transition(
    document_id: uuid.UUID,
    body: MailTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(MailDocument).filter(MailDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not _can_access_document(current_user, document):
        raise HTTPException(status_code=403, detail="Access denied")

    workflow_service.apply_transition(
        db,
        document,
        current_user,
        body.action_key,
        notes=body.notes,
        assigned_to_id=body.assigned_to_id,
        current_department=body.current_department,
    )
    db.refresh(document)

    await notify_after_mail_transition(
        db, document, body.action_key, current_user.id
    )

    pending = document.id in _pending_mail_deletion_ids(db)
    return _doc_out(document, pending, current_user)


@router.post("/{document_id}/executive-archive", response_model=MailDocumentSchema)
async def executive_archive_mail_document(
    document_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Archivage direct par la direction (sans enchaîner les étapes workflow). Master ou director uniquement."""
    if not current_user.has_any_role("master", "director"):
        raise HTTPException(
            status_code=403,
            detail="Only master and director can use executive mail archive",
        )
    document = db.query(MailDocument).filter(MailDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not _can_access_document(current_user, document):
        raise HTTPException(status_code=403, detail="Access denied")
    if document.status == MailStatus.ARCHIVED:
        raise HTTPException(status_code=400, detail="Document is already archived")

    old_status = document.status
    document.status = MailStatus.ARCHIVED
    document.archived_at = datetime.utcnow()

    history = WorkflowHistory(
        document_id=document.id,
        from_status=old_status,
        to_status=MailStatus.ARCHIVED,
        action="executive_archive",
        performed_by=current_user.id,
        notes="Archivage direct (master / direction)",
    )
    db.add(history)
    state = WorkflowState(
        document_id=document.id,
        status=MailStatus.ARCHIVED,
        department=document.current_department,
        notes="executive_archive",
    )
    db.add(state)

    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")
    audit_logger.log_action(
        action="mail_executive_archive",
        user_id=current_user.id,
        resource_type="mail_document",
        resource_id=document.id,
        details={"from_status": old_status.value if hasattr(old_status, "value") else str(old_status)},
        ip_address=ip,
        user_agent=ua,
    )

    db.commit()
    db.refresh(document)
    pending = document.id in _pending_mail_deletion_ids(db)
    return _doc_out(document, pending, current_user)


@router.get("/{document_id}", response_model=MailDocumentSchema)
async def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(MailDocument).filter(MailDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not _can_access_document(current_user, document):
        raise HTTPException(status_code=403, detail="Access denied")

    pending = document.id in _pending_mail_deletion_ids(db)
    return _doc_out(document, pending, current_user)


@router.post("/{document_id}/deletion-request")
async def request_mail_deletion(
    document_id: uuid.UUID,
    body: DeletionRequestCreateBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(MailDocument).filter(MailDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not user_has_permission(current_user, "mail.request_delete"):
        raise HTTPException(status_code=403, detail="Not enough permissions to request deletion")
    if not _can_access_document(current_user, document):
        raise HTTPException(status_code=403, detail="Access denied")
    dup = (
        db.query(DeletionRequest)
        .filter(
            DeletionRequest.target_type == TARGET_MAIL,
            DeletionRequest.target_id == document_id,
            DeletionRequest.status == STATUS_PENDING,
        )
        .first()
    )
    if dup:
        raise HTTPException(status_code=400, detail="A deletion request is already pending for this document")
    req = DeletionRequest(
        target_type=TARGET_MAIL,
        target_id=document_id,
        reason=body.reason,
        requested_by=current_user.id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    reviewers = user_ids_for_deletion_reviewers(db)
    emit_in_app(
        db,
        reviewers,
        "Deletion request (mail)",
        f"{document.reference_number} — review required.",
        {"type": "deletion_request", "target": "mail", "document_id": str(document_id)},
    )
    return {"id": str(req.id), "message": "Deletion request submitted"}


@router.delete("/{document_id}")
async def delete_mail_document_endpoint(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_has_permission(current_user, "mail.delete"):
        raise HTTPException(status_code=403, detail="Not enough permissions to delete mail")
    document = db.query(MailDocument).filter(MailDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not _can_access_document(current_user, document):
        raise HTTPException(status_code=403, detail="Access denied")
    from app.services.mail_purge_service import purge_mail_document

    ok = purge_mail_document(db, document_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found")
    db.commit()
    return {"message": "Document deleted"}


@router.put("/{document_id}", response_model=MailDocumentSchema)
async def update_document(
    document_id: uuid.UUID,
    document_update: MailDocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(MailDocument).filter(MailDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not user_has_permission(current_user, "mail.update"):
        raise HTTPException(status_code=403, detail="Not enough permissions to update mail")
    if not current_user.has_any_role("master", "director"):
        if document.assigned_to != current_user.id and document.created_by != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")

    previous_assignee = document.assigned_to
    update_data = document_update.model_dump(exclude_unset=True)

    if "direction" in update_data:
        d = update_data.pop("direction")
        wd = mail_workflow_engine.get_active_definition(db, d)
        document.direction = d
        document.workflow_definition_id = wd.id if wd else None

    for field, value in update_data.items():
        setattr(document, field, value)

    db.commit()
    db.refresh(document)

    if document.assigned_to and document.assigned_to != previous_assignee:
        await notify_after_mail_transition(
            db, document, "assign", current_user.id
        )

    pending = document.id in _pending_mail_deletion_ids(db)
    return _doc_out(document, pending, current_user)


@router.post("/{document_id}/assign")
async def assign_document(
    document_id: uuid.UUID,
    assigned_to_id: uuid.UUID,
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not user_has_any_permission(
        current_user, "mail.update", "mail.workflow.assign", "mail.workflow.all"
    ):
        raise HTTPException(status_code=403, detail="Not enough permissions to assign mail")
    document = db.query(MailDocument).filter(MailDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    assigned_to = db.query(User).filter(User.id == assigned_to_id).first()
    if not assigned_to:
        raise HTTPException(status_code=404, detail="User not found")

    workflow_service.assign_document(db, document, assigned_to, current_user, notes)
    db.refresh(document)
    await notify_after_mail_transition(db, document, "assign", current_user.id)
    return {"message": "Document assigned successfully"}


@router.get("/{document_id}/history", response_model=List[WorkflowHistory])
async def get_document_history(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.query(MailDocument).filter(MailDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not _can_access_document(current_user, document):
        raise HTTPException(status_code=403, detail="Access denied")

    return workflow_service.get_workflow_history(db, document_id)


@router.get("/{document_id}/file")
async def download_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from fastapi.responses import Response
    import mimetypes

    document = db.query(MailDocument).filter(MailDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not _can_access_document(current_user, document):
        raise HTTPException(status_code=403, detail="Access denied")

    file_content = await storage_service.get_file(document.file_path)

    mime_type = document.mime_type
    if not mime_type or mime_type == "application/octet-stream":
        mime_type, _ = mimetypes.guess_type(document.file_name)
        if not mime_type:
            mime_type = "application/octet-stream"

    content_disposition = (
        "inline"
        if mime_type in ["application/pdf", "image/png", "image/jpeg", "image/jpg", "image/tiff"]
        else "attachment"
    )

    safe_filename = document.file_name.encode("ascii", "ignore").decode("ascii")

    return Response(
        content=file_content,
        media_type=mime_type,
        headers={
            "Content-Disposition": f'{content_disposition}; filename="{safe_filename}"',
            "Content-Type": mime_type,
            "Cache-Control": "public, max-age=3600",
        },
    )
