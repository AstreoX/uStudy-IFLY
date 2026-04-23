"""笔记模块 Pydantic 模型"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from db.models import NoteAttachmentType


# ============ 附件 ============


class NoteAttachmentResponse(BaseModel):
    id: UUID
    note_id: UUID
    attachment_type: NoteAttachmentType
    file_url: Optional[str] = None
    original_filename: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    link_url: Optional[str] = None
    link_title: Optional[str] = None
    sort_order: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class AddLinkRequest(BaseModel):
    link_url: str = Field(..., min_length=1, max_length=2048)
    link_title: Optional[str] = Field(None, max_length=500)


# ============ 笔记 ============


class NoteCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = None
    node_id: Optional[UUID] = None
    sort_order: int = Field(default=0)


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    content: Optional[str] = None
    node_id: Optional[UUID] = None
    sort_order: Optional[int] = None


class NoteResponse(BaseModel):
    id: UUID
    space_id: UUID
    node_id: Optional[UUID] = None
    node_label: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    note_type: str = "text"
    metadata_: Optional[dict] = None
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime
    attachments: list[NoteAttachmentResponse] = []
    creator_user_id: Optional[UUID] = None
    creator_nickname: Optional[str] = None

    model_config = {"from_attributes": True}


class NoteListItem(BaseModel):
    id: UUID
    space_id: UUID
    node_id: Optional[UUID] = None
    node_label: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    note_type: str = "text"
    metadata_: Optional[dict] = None
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime
    attachment_count: int = 0
    creator_user_id: Optional[UUID] = None
    creator_nickname: Optional[str] = None

    model_config = {"from_attributes": True}
