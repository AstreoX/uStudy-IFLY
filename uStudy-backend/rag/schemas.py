"""RAG API schemas"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """搜索请求"""

    query: str = Field(..., min_length=1, max_length=1000, description="搜索查询")
    top_k: int = Field(default=10, ge=1, le=50, description="返回结果数量")
    rerank: bool = Field(default=False, description="是否启用重排序")


class SearchResultItem(BaseModel):
    """搜索结果项"""

    chunk_id: UUID
    document_id: UUID
    content: str
    score: float = Field(description="最终排序分数")
    retrieval_score: float | None = Field(default=None, description="检索阶段分数")
    rerank_score: float | None = Field(default=None, description="重排序分数")
    retrieval_source: str = Field(
        default="dense", description="结果来源：dense/sparse/merged"
    )
    document_title: str | None
    document_filename: str | None
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
    chunk_count: int | None
    processed_chunks: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    generation: int = 1
    stage: str = "queued"
    page_count: int | None = None
    processed_pages: int = 0
    asset_count: int = 0
    outline_status: str | None = None
    attempt_count: int = 0
    next_retry_at: datetime | None = None
    error_code: str | None = None
    warning_code: str | None = None
