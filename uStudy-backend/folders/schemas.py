"""文件夹模块 Pydantic 模型"""

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from db.models import FolderContentType


class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[UUID] = None
    content_type: FolderContentType


class FolderUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)


class FolderResponse(BaseModel):
    id: UUID
    space_id: UUID
    parent_id: Optional[UUID] = None
    content_type: FolderContentType
    name: str
    creator_user_id: Optional[UUID] = None
    visibility: Literal["shared", "private"] = "shared"
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime
    children_count: int = 0
    items_count: int = 0

    model_config = {"from_attributes": True}


class MoveItemsRequest(BaseModel):
    item_ids: list[UUID] = Field(..., min_length=1)
    target_folder_id: Optional[UUID] = None


class MoveFolderRequest(BaseModel):
    target_parent_id: Optional[UUID] = None
