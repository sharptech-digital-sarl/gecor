from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
import uuid


class PublicInformationPostBase(BaseModel):
    title: str
    body: str
    sort_order: int = 0
    published: bool = True


class PublicInformationPostCreate(PublicInformationPostBase):
    pass


class PublicInformationPostUpdate(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    sort_order: Optional[int] = None
    published: Optional[bool] = None


class PublicInformationPostOut(PublicInformationPostBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublicInformationPostPublicOut(BaseModel):
    """Published fields only for anonymous home page."""

    id: uuid.UUID
    title: str
    body: str
    sort_order: int
    created_at: datetime
    updated_at: datetime
    author_username: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
