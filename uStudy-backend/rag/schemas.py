"""RAG API schemas"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """搜索请求"""

    query: str = Field(..., min_length=1, max_length=1000, description="搜索查询")
    top_k: int = Field(default=10, ge=1, le=50, description="返回结果数量")
    rerank: bool = Field(default=True, description="是否启用重排序")


class SearchResultItem(BaseModel):
    """搜索结果项"""

    chunk_id: UUID
    document_id: UUID
    content: str
    score: float = Field(description="向量相似度分数")
    rerank_score: Optional[float] = Field(default=None, description="重排序分数")
    document_title: str
    document_filename: Optional[str]
    metadata: dict = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """搜索响应"""

    results: list[SearchResultItem]
    total: int
    query: str


class ProcessingStatusResponse(BaseModel):
    """处理状态响应"""

    document_id: UUID
    status: str
    chunk_count: Optional[int]
    processed_chunks: int
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
