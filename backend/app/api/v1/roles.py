from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.permissions import PERMISSIONS_CATALOG
from app.core.security import require_role
from app.models.role import Role
from app.models.user import User, UserRole
from app.models.user_role import user_roles
from app.schemas.role import RoleCreate, RoleOut, RolePermissionsUpdate
from app.schemas.user import BulkDeleteIds

router = APIRouter()


def _role_ids_for_user(user: User) -> set:
    """Identifiants des groupes auxquels l’utilisateur est encore rattaché."""
    return {r.id for r in (user.roles or [])}


@router.get("/permissions-catalog")
async def get_permissions_catalog(
    current_user: User = Depends(require_role(UserRole.MASTER, UserRole.DIRECTOR, "admin")),
):
    """Liste des permissions disponibles (clé + libellé)."""
    return PERMISSIONS_CATALOG


@router.get("/", response_model=List[RoleOut])
async def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER, UserRole.DIRECTOR, "admin")),
):
    roles = db.query(Role).order_by(Role.name).all()
    return roles


@router.post("/", response_model=RoleOut)
async def create_role(
    body: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER)),
):
    """Créer un nouveau groupe (rôle) avec un nom technique unique."""
    if body.name.lower() in ("master", "admin"):
        raise HTTPException(
            status_code=400,
            detail="Reserved role name: master and admin are system roles",
        )
    existing = db.query(Role).filter(func.lower(Role.name) == body.name.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="A role with this name already exists")
    role = Role(
        name=body.name,
        description=body.description,
        permissions=list(body.permissions),
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.post("/bulk-delete")
async def bulk_delete_roles(
    body: BulkDeleteIds,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER)),
):
    """Supprime plusieurs groupes (rôles) en une requête (mêmes règles que DELETE /{role_id})."""
    my_role_ids = _role_ids_for_user(current_user)
    deleted: List[str] = []
    skipped: List[dict] = []
    for rid in body.ids:
        role = db.query(Role).filter(Role.id == rid).first()
        if not role:
            skipped.append({"id": str(rid), "reason": "not_found"})
            continue
        if rid in my_role_ids:
            skipped.append({"id": str(rid), "reason": "assigned_to_current_user"})
            continue
        n_users = db.execute(
            select(func.count()).select_from(user_roles).where(user_roles.c.role_id == rid)
        ).scalar_one()
        if n_users and int(n_users) > 0:
            skipped.append({"id": str(rid), "reason": "users_assigned"})
            continue
        db.delete(role)
        deleted.append(str(rid))
    db.commit()
    return {
        "deleted": deleted,
        "skipped": skipped,
        "deleted_count": len(deleted),
    }


@router.put("/{role_id}/permissions", response_model=RoleOut)
async def update_role_permissions(
    role_id: uuid.UUID,
    body: RolePermissionsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER)),
):
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    role.permissions = list(body.permissions)
    db.commit()
    db.refresh(role)
    return role


@router.delete("/{role_id}")
async def delete_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.MASTER)),
):
    """Supprimer un groupe. Interdit si le compte connecté est encore dans ce groupe, ou si d’autres utilisateurs y sont encore affectés."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    if role_id in _role_ids_for_user(current_user):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a role assigned to your account. Assign yourself to another group first.",
        )
    n_users = db.execute(
        select(func.count()).select_from(user_roles).where(user_roles.c.role_id == role_id)
    ).scalar_one()
    if n_users and int(n_users) > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete this role: reassign users to another group first",
        )
    db.delete(role)
    db.commit()
    return {"message": "Role deleted"}
