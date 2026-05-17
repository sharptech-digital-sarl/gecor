import re
from pydantic import BaseModel, ConfigDict, field_validator
from typing import List, Optional, Any
import uuid

from app.core.permissions import PERMISSIONS_CATALOG

_VALID_KEYS = {p["key"] for p in PERMISSIONS_CATALOG}
_ROLE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,47}$")


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    permissions: List[str] = []

    model_config = ConfigDict(from_attributes=True)

    @field_validator("permissions", mode="before")
    @classmethod
    def none_to_empty(cls, v: Any) -> List[str]:
        return v if v is not None else []


def _validate_permission_keys(v: List[str]) -> List[str]:
    bad = [k for k in v if k not in _VALID_KEYS]
    if bad:
        raise ValueError(f"Unknown permission keys: {bad}")
    return v


class RolePermissionsUpdate(BaseModel):
    permissions: List[str]

    @field_validator("permissions")
    @classmethod
    def keys_must_be_known(cls, v: List[str]) -> List[str]:
        return _validate_permission_keys(v)


class RoleCreate(BaseModel):
    """Création d'un groupe / rôle (nom technique unique, permissions initiales optionnelles)."""

    name: str
    description: Optional[str] = None
    permissions: List[str] = []

    @field_validator("name")
    @classmethod
    def normalize_role_name(cls, v: str) -> str:
        n = v.strip().lower()
        if not _ROLE_NAME_RE.match(n):
            raise ValueError(
                "Invalid role name: start with a letter, then lowercase letters, digits or underscore; 2–48 chars."
            )
        return n

    @field_validator("permissions")
    @classmethod
    def keys_must_be_known(cls, v: List[str]) -> List[str]:
        return _validate_permission_keys(v)
