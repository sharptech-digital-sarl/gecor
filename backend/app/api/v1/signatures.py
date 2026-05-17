from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
import base64
import os
import uuid

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.mail import MailDocument
from app.models.signature import Signature
from app.schemas.signature import Signature as SignatureSchema, SignatureCreate
from app.services.storage_service import storage_service

router = APIRouter()


@router.post("/", response_model=SignatureSchema)
async def create_signature(
    signature_data: SignatureCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create electronic signature for a document"""
    # Verify document exists
    document = db.query(MailDocument).filter(MailDocument.id == signature_data.document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check permissions
    if not current_user.has_any_role("master", "director", "secretary"):
        if document.assigned_to != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    # Decode and save signature image
    try:
        # Remove data URL prefix if present
        if signature_data.signature_data.startswith("data:image"):
            signature_data.signature_data = signature_data.signature_data.split(",")[1]
        
        image_bytes = base64.b64decode(signature_data.signature_data)
        
        # Save signature image
        signature_filename = f"signature_{document.id}_{current_user.id}_{datetime.utcnow().timestamp()}.png"
        signature_path = await storage_service.save_file(
            image_bytes,
            signature_filename,
            subdirectory="signatures"
        )
        
        # Store signature_data with data URL prefix for frontend compatibility
        # The frontend expects data:image/png;base64,... format
        stored_signature_data = signature_data.signature_data
        if not stored_signature_data.startswith("data:image/"):
            # Add data URL prefix if not present
            stored_signature_data = f"data:image/png;base64,{stored_signature_data}"
        
        # Create signature record
        signature = Signature(
            document_id=signature_data.document_id,
            user_id=current_user.id,
            signature_image_path=signature_path,
            signature_data=stored_signature_data,
            annotations=signature_data.annotations,
            comments=signature_data.comments,
            signed_at=datetime.utcnow()
        )
        
        db.add(signature)
        db.commit()
        db.refresh(signature)
        
        return signature
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process signature: {str(e)}")


@router.get("/", response_model=List[SignatureSchema])
async def list_signatures(
    document_id: Optional[uuid.UUID] = Query(None, description="Filter by document ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get signatures, optionally filtered by document ID"""
    query = db.query(Signature)
    
    if document_id:
        # Verify document exists and check permissions
        document = db.query(MailDocument).filter(MailDocument.id == document_id).first()
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Check permissions
        if not current_user.has_any_role("master", "director"):
            if document.assigned_to != current_user.id and document.created_by != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied")
        
        query = query.filter(Signature.document_id == document_id)
    else:
        # If no document_id, only return signatures for documents the user can access
        if not current_user.has_any_role("master", "director"):
            # Get document IDs the user can access
            accessible_doc_ids = db.query(MailDocument.id).filter(
                (MailDocument.assigned_to == current_user.id) |
                (MailDocument.created_by == current_user.id)
            ).all()
            accessible_doc_ids = [doc_id[0] for doc_id in accessible_doc_ids]
            if accessible_doc_ids:
                query = query.filter(Signature.document_id.in_(accessible_doc_ids))
            else:
                # User has no accessible documents, return empty list
                return []
    
    signatures = query.all()
    
    # Ensure signature_data is in data URL format for frontend
    for sig in signatures:
        if sig.signature_data and not sig.signature_data.startswith("data:image/"):
            # Convert base64 to data URL if needed
            sig.signature_data = f"data:image/png;base64,{sig.signature_data}"
        elif not sig.signature_data and sig.signature_image_path:
            # If signature_data is missing but image exists, load it and convert to data URL
            try:
                image_bytes = await storage_service.get_file(sig.signature_image_path)
                import base64
                base64_data = base64.b64encode(image_bytes).decode('utf-8')
                sig.signature_data = f"data:image/png;base64,{base64_data}"
            except Exception:
                # If we can't load the image, leave signature_data as None
                pass
    
    return signatures


@router.get("/document/{document_id}", response_model=List[SignatureSchema])
async def get_document_signatures(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all signatures for a document"""
    document = db.query(MailDocument).filter(MailDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check permissions
    if not current_user.has_any_role("master", "director"):
        if document.assigned_to != current_user.id and document.created_by != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    signatures = db.query(Signature).filter(Signature.document_id == document_id).all()
    
    # Ensure signature_data is in data URL format for frontend
    for sig in signatures:
        if sig.signature_data and not sig.signature_data.startswith("data:image/"):
            # Convert base64 to data URL if needed
            sig.signature_data = f"data:image/png;base64,{sig.signature_data}"
        elif not sig.signature_data and sig.signature_image_path:
            # If signature_data is missing but image exists, load it and convert to data URL
            try:
                image_bytes = await storage_service.get_file(sig.signature_image_path)
                import base64
                base64_data = base64.b64encode(image_bytes).decode('utf-8')
                sig.signature_data = f"data:image/png;base64,{base64_data}"
            except Exception:
                # If we can't load the image, leave signature_data as None
                pass
    
    return signatures


@router.get("/{signature_id}/image")
async def get_signature_image(
    signature_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get signature image"""
    from fastapi.responses import Response
    
    signature = db.query(Signature).filter(Signature.id == signature_id).first()
    if not signature:
        raise HTTPException(status_code=404, detail="Signature not found")
    
    # Check permissions
    document = db.query(MailDocument).filter(MailDocument.id == signature.document_id).first()
    if not current_user.has_any_role("master", "director"):
        if document.assigned_to != current_user.id and document.created_by != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    image_content = await storage_service.get_file(signature.signature_image_path)
    
    return Response(
        content=image_content,
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename=signature_{signature_id}.png"}
    )

