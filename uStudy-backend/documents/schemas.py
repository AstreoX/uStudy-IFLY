"""Pydantic schemas for documents module."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


class LinkCreate(BaseModel):
    """创建链接请求"""

    title: str = Field(..., min_length=1, max_length=255)
    url: HttpUrl


class DocumentResponse(BaseModel):
    """文档/链接响应"""

    id: UUID
    space_id: UUID
    doc_type: str
    title: str
    url: str
    original_filename: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """文档列表响应"""

    documents: list[DocumentResponse]
    total: int
