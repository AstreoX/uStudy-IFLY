"""RAG API 路由"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from config import get_settings
from db.database import get_db
from db.models import DocumentProcessingTask, Space, SpaceDocument, User
from rag.retrieval import HybridSearchService, VectorSearchService
from rag.schemas import (
    ProcessingStatusResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)

settings = get_settings()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["RAG"])


async def verify_space_access(
    db: AsyncSession, space_id: UUID, user_id: UUID
) -> Space:
    """验证用户是否有权访问该空间"""
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()

    if not space:
        raise HTTPException(status_code=404, detail="学习空间不存在")

    if space.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问该学习空间")

    return space


@router.post("/spaces/{space_id}/search", response_model=SearchResponse)
async def search_documents(
    space_id: UUID,
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    在学习空间中搜索文档

    使用向量相似度进行语义搜索，可选启用 Cross-Encoder 重排序。
    """
    await verify_space_access(db, space_id, current_user.id)

    # 选择搜索服务
    if settings.hybrid_search_enabled:
        search_service = HybridSearchService(db)
    else:
        search_service = VectorSearchService(db)

    search_results = await search_service.search(
        query=request.query,
        space_id=space_id,
        top_k=request.top_k,
    )

    if not search_results:
        return SearchResponse(results=[], total=0, query=request.query)

    results = [
        SearchResultItem(
            chunk_id=r.chunk_id,
            document_id=r.document_id,
            content=r.content,
            score=r.score,
            document_title=r.document_title,
            document_filename=r.document_filename,
            metadata=r.metadata,
        )
        for r in search_results
    ]

    return SearchResponse(
        results=results,
        total=len(results),
        query=request.query,
    )


@router.get(
    "/spaces/{space_id}/documents/{document_id}/processing",
    response_model=ProcessingStatusResponse,
)
async def get_processing_status(
    space_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取文档处理状态"""
    await verify_space_access(db, space_id, current_user.id)

    # 验证文档属于该空间
    doc_result = await db.execute(
        select(SpaceDocument).where(
            SpaceDocument.id == document_id, SpaceDocument.space_id == space_id
        )
    )
    document = doc_result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 获取处理任务
    task_result = await db.execute(
        select(DocumentProcessingTask).where(
            DocumentProcessingTask.document_id == document_id
        )
    )
    task = task_result.scalar_one_or_none()

    if not task:
        # 没有处理任务，返回 pending 状态
        return ProcessingStatusResponse(
            document_id=document_id,
            status="not_started",
            chunk_count=None,
            error_message=None,
            started_at=None,
            completed_at=None,
            created_at=document.created_at,
        )

    return ProcessingStatusResponse(
        document_id=document_id,
        status=task.status.value,
        chunk_count=task.chunk_count,
        error_message=task.error_message,
        started_at=task.started_at,
        completed_at=task.completed_at,
        created_at=task.created_at,
    )


@router.post("/spaces/{space_id}/documents/{document_id}/reprocess")
async def reprocess_document(
    space_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    重新处理文档

    删除现有切片并重新进行切片和向量化。
    """
    from documents.service import schedule_document_processing

    await verify_space_access(db, space_id, current_user.id)

    # 验证文档属于该空间
    doc_result = await db.execute(
        select(SpaceDocument).where(
            SpaceDocument.id == document_id, SpaceDocument.space_id == space_id
        )
    )
    document = doc_result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 触发重新处理
    schedule_document_processing(document_id)

    return {"message": "文档处理任务已重新调度", "document_id": str(document_id)}
