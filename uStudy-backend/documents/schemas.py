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


class CrawlImportRequest(BaseModel):
    """深度爬取导入请求"""

    url: HttpUrl
    max_pages: int = Field(default=5, ge=1, le=20)
    url_pattern: Optional[str] = Field(default=None, description="URL 过滤正则表达式")


class CrawlImportResponse(BaseModel):
    """深度爬取导入响应"""

    discovered_urls: list[str]
    document_ids: list[UUID]
    total: int
