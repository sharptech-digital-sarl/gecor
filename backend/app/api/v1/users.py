from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
import uuid

from app.core.audit import audit_logger
from app.core.config import settings
from app.core.database import get_db
from app.core.request_ip import get_client_ip
from app.core.security import get_current_user, get_password_hash, require_role
from app.models.role import Role
from app.models.user import User, UserRole
from app.models.password_reset_request import PasswordResetRequest, PasswordResetRequestStatus
from app.schemas.user import (
    User as UserSchema,
    UserAdminCreate,
    UserUpdate,
    VisitHostCandidate,
    BulkDeleteIds,
    AdminPasswordResetRequest,
    AdminPasswordResetOut,
)
from app.schemas.password_reset_request import PasswordResetRequestOut, PasswordResetRequestResolve

router = APIRouter()


def _normalize_policy_password_from_settings(raw: Optional[str]) -> str:
    """Valeur .env : retire guillemets accidentels autour du mot de passe politique."""
    s = (raw or "").strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1].strip()
    return s


def _pwd_reset_to_out(row: PasswordResetRequest) -> PasswordResetRequestOut:
    u = row.user
    return PasswordResetRequestOut(
        id=row.id,
        email_requested=row.email_requested,
        user_id=row.user_id,
        requester_username=u.username if u else None,
        requester_full_name=u.full_name if u else None,
        requester_message=row.requester_message,
        status=row.status,
        created_at=row.created_at,
        last_master_reminder_at=row.last_master_reminder_at,
        resolved_at=row.resolved_at,
        resolution_note=row.resolution_note,
        password_reset_at=row.password_reset_at,
        password_reset_mode=row.password_reset_mode,
        password_reset_must_change=row.password_reset_must_change,
    )


def _plain_password_for_admin_reset(body: AdminPasswordResetRequest) -> str:
    if body.mode == "policy":
        raw = _normalize_policy_password_from_settings(settings.PASSWORD_RESET_POLICY_DEFAULT)
        if len(raw) < 8:
            raise HTTPException(
                status_code=503,
                detail="PASSWORD_RESET_POLICY_DEFAULT is not set or shorter than 8 characters",
            )
        return raw
    return (body.new_password or "").strip()


@router.get("/visit-host-candidates", response_model=List[VisitHostCandidate])
async def list_visit_host_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_role(
            UserRole.SECRETARY,
            UserRole.RECEPTIONIST,
            UserRole.MASTER,
            UserRole.DIRECTOR,
        )
    ),
):
    """Utilisateurs actifs pouvant recevoir une visite (tous sauf le rôle master)."""
    users = (
        db.query(User)
        .options(joinedload(User.roles))
        .filter(User.is_active.is_(True))
        .order_by(func.lower(User.full_name))
        .all()
    )
    out: List[VisitHostCandidate] = []
    for u in users:
        if u.has_role("master"):
            continue
        out.append(
            VisitHostCandidate(
                id=u.id,
                full_name=u.full_name,
                username=u.username,
                role=u.role,
            )
        )
    return out


@router.get("/", response_model=List[UserSchema])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER, UserRole.DIRECTOR, "admin")),
):
    """Get list of users"""
    users = (
        db.query(User)
        .options(joinedload(User.roles))
        .offset(skip)
        .limit(limit)
        .all()
    )
    return users


@router.post("/", response_model=UserSchema)
async def create_user(
    body: UserAdminCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER)),
):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    role_row = db.query(Role).filter(func.lower(Role.name) == body.role.lower()).first()
    if not role_row:
        raise HTTPException(status_code=400, detail="Unknown role")
    user = User(
        email=body.email,
        username=body.username,
        full_name=body.full_name,
        hashed_password=get_password_hash(body.password),
        is_active=True,
        is_superuser=False,
    )
    user.roles = [role_row]
    db.add(user)
    db.commit()
    db.refresh(user)
    user = db.query(User).options(joinedload(User.roles)).filter(User.id == user.id).first()
    return user


@router.post("/bulk-delete")
async def bulk_delete_users(
    body: BulkDeleteIds,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER)),
):
    """Supprime plusieurs utilisateurs en une requête (master uniquement)."""
    deleted: List[str] = []
    skipped: List[dict] = []
    for uid in body.ids:
        if uid == current_user.id:
            skipped.append({"id": str(uid), "reason": "cannot_delete_self"})
            continue
        user = db.query(User).filter(User.id == uid).first()
        if not user:
            skipped.append({"id": str(uid), "reason": "not_found"})
            continue
        db.delete(user)
        deleted.append(str(uid))
    db.commit()
    return {
        "deleted": deleted,
        "skipped": skipped,
        "deleted_count": len(deleted),
    }


@router.get("/password-reset-requests", response_model=List[PasswordResetRequestOut])
async def list_password_reset_requests(
    status_filter: Optional[str] = Query(None, description="pending | completed | rejected | all"),
    limit: int = Query(200, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER)),
):
    """File des demandes « mot de passe oublié » (master uniquement)."""
    q = db.query(PasswordResetRequest).options(joinedload(PasswordResetRequest.user))
    sf = (status_filter or "all").strip().lower()
    if sf == "pending":
        q = q.filter(PasswordResetRequest.status == PasswordResetRequestStatus.PENDING.value)
    elif sf in ("completed", "rejected"):
        q = q.filter(PasswordResetRequest.status == sf)
    elif sf != "all":
        raise HTTPException(status_code=400, detail="Invalid status_filter")
    rows = q.order_by(PasswordResetRequest.created_at.desc()).limit(limit).all()
    return [_pwd_reset_to_out(r) for r in rows]


@router.post("/password-reset-requests/{request_id}/resolve", response_model=PasswordResetRequestOut)
async def resolve_password_reset_request(
    request_id: uuid.UUID,
    body: PasswordResetRequestResolve,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER)),
):
    row = (
        db.query(PasswordResetRequest)
        .options(joinedload(PasswordResetRequest.user))
        .filter(PasswordResetRequest.id == request_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if row.status != PasswordResetRequestStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Request is already resolved")

    row.status = (
        PasswordResetRequestStatus.COMPLETED.value
        if body.action == "completed"
        else PasswordResetRequestStatus.REJECTED.value
    )
    row.resolved_at = datetime.utcnow()
    row.resolved_by_user_id = current_user.id
    row.resolution_note = (body.note or "").strip() or None
    db.add(row)
    db.commit()
    db.refresh(row)

    audit_logger.log_action(
        action="password_reset_request_resolved",
        user_id=current_user.id,
        resource_type="password_reset_request",
        resource_id=row.id,
        details={"action": body.action, "request_email": row.email_requested},
    )

    return _pwd_reset_to_out(row)


@router.post("/password-reset-requests/{request_id}/reset-password", response_model=AdminPasswordResetOut)
async def reset_password_from_reset_request(
    request_id: uuid.UUID,
    body: AdminPasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER)),
):
    """Réinitialise le mot de passe du compte lié à la demande et enregistre la trace côté demande."""
    row = (
        db.query(PasswordResetRequest)
        .options(joinedload(PasswordResetRequest.user))
        .filter(PasswordResetRequest.id == request_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    if not row.user_id:
        raise HTTPException(
            status_code=400,
            detail="No user account is linked to this request; reset the password from user administration",
        )
    if row.status != PasswordResetRequestStatus.PENDING.value:
        raise HTTPException(status_code=400, detail="Request is no longer pending")

    user = (
        db.query(User)
        .options(joinedload(User.roles))
        .filter(User.id == row.user_id)
        .first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    plain = _plain_password_for_admin_reset(body)
    user.hashed_password = get_password_hash(plain)
    user.password_must_change = body.must_change_on_next_login

    now = datetime.utcnow()
    row.password_reset_at = now
    row.password_reset_by_user_id = current_user.id
    row.password_reset_mode = "policy" if body.mode == "policy" else "custom"
    row.password_reset_must_change = body.must_change_on_next_login
    row.status = PasswordResetRequestStatus.COMPLETED.value
    row.resolved_at = now
    row.resolved_by_user_id = current_user.id

    db.add(user)
    db.add(row)
    db.commit()
    db.refresh(user)
    db.refresh(row)

    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    audit_logger.log_action(
        action="admin_password_reset",
        user_id=current_user.id,
        resource_type="user",
        resource_id=user.id,
        details={
            "target_username": user.username,
            "mode": body.mode,
            "must_change_on_next_login": body.must_change_on_next_login,
            "from_password_reset_request_id": str(request_id),
        },
        ip_address=client_ip,
        user_agent=user_agent,
    )

    if body.mode == "policy":
        return AdminPasswordResetOut(
            message="Password reset from policy default; share with the user if needed.",
            temporary_password=plain,
        )
    return AdminPasswordResetOut(message="Password has been set.", temporary_password=None)


@router.get("/{user_id}", response_model=UserSchema)
async def read_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user by ID"""
    user = (
        db.query(User)
        .options(joinedload(User.roles))
        .filter(User.id == user_id)
        .first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Users can only view their own profile unless they're admin/director/master
    if current_user.id != user_id and not current_user.has_any_role("master", "director", "admin"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    return user


@router.put("/{user_id}", response_model=UserSchema)
async def update_user(
    user_id: uuid.UUID,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update user"""
    user = (
        db.query(User)
        .options(joinedload(User.roles))
        .filter(User.id == user_id)
        .first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Only admin can update other users, or users can update themselves
    if current_user.id != user_id and not current_user.has_role("master"):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # Only admin can change roles
    if user_update.role and not current_user.has_role("master"):
        raise HTTPException(status_code=403, detail="Only master can change user roles")

    update_data = user_update.model_dump(exclude_unset=True)
    new_role = update_data.pop("role", None)
    if "email" in update_data:
        other = (
            db.query(User)
            .filter(User.email == update_data["email"], User.id != user_id)
            .first()
        )
        if other:
            raise HTTPException(status_code=400, detail="Email already registered")
    if "username" in update_data:
        other = (
            db.query(User)
            .filter(User.username == update_data["username"], User.id != user_id)
            .first()
        )
        if other:
            raise HTTPException(status_code=400, detail="Username already taken")
    for field, value in update_data.items():
        setattr(user, field, value)
    if new_role is not None:
        role_row = db.query(Role).filter(func.lower(Role.name) == new_role.strip().lower()).first()
        if not role_row:
            raise HTTPException(status_code=400, detail="Unknown role")
        user.roles = [role_row]

    if user_id == current_user.id and update_data.get("is_active") is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    db.commit()
    db.refresh(user)
    user = db.query(User).options(joinedload(User.roles)).filter(User.id == user.id).first()
    return user


@router.post("/{user_id}/reset-password", response_model=AdminPasswordResetOut)
async def admin_reset_user_password(
    user_id: uuid.UUID,
    body: AdminPasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER)),
):
    """Réinitialise le mot de passe d’un utilisateur (master uniquement)."""
    user = (
        db.query(User)
        .options(joinedload(User.roles))
        .filter(User.id == user_id)
        .first()
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    plain = _plain_password_for_admin_reset(body)

    user.hashed_password = get_password_hash(plain)
    user.password_must_change = body.must_change_on_next_login
    db.add(user)
    db.commit()
    db.refresh(user)

    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    audit_logger.log_action(
        action="admin_password_reset",
        user_id=current_user.id,
        resource_type="user",
        resource_id=user.id,
        details={
            "target_username": user.username,
            "mode": body.mode,
            "must_change_on_next_login": body.must_change_on_next_login,
        },
        ip_address=client_ip,
        user_agent=user_agent,
    )

    if body.mode == "policy":
        return AdminPasswordResetOut(
            message="Password reset; communicate the temporary password to the user.",
            temporary_password=plain,
        )
    return AdminPasswordResetOut(
        message="Password has been set.",
        temporary_password=None,
    )


@router.delete("/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER)),
):
    """Delete a user account (master only)."""
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Master cannot delete their own account")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

