"""API routes for documents module."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User

from .schemas import (
    CrawlImportRequest,
    CrawlImportResponse,
    DocumentListResponse,
    DocumentResponse,
    LinkCreate,
)
from .service import (
    crawl_and_import,
    create_link,
    delete_document,
    get_space_documents,
    upload_document,
)

router = APIRouter(prefix="/api/spaces", tags=["documents"])


@router.post("/{space_id}/documents/link", response_model=DocumentResponse)
async def add_link(
    space_id: UUID,
    data: LinkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """添加链接到学习空间"""
    document = await create_link(
        db=db,
        space_id=space_id,
        user_id=current_user.id,
        title=data.title,
        url=str(data.url),
    )
    return document


@router.post("/{space_id}/documents/upload", response_model=DocumentResponse)
async def upload_document_endpoint(
    space_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传文档到学习空间"""
    document = await upload_document(
        db=db,
        space_id=space_id,
        user_id=current_user.id,
        file=file,
        user=current_user,
    )
    return document


@router.get("/{space_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    space_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取学习空间的所有文档和链接"""
    documents = await get_space_documents(
        db=db,
        space_id=space_id,
        user_id=current_user.id,
    )
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
        total=len(documents),
    )


@router.post("/{space_id}/documents/crawl", response_model=CrawlImportResponse)
async def crawl_import(
    space_id: UUID,
    data: CrawlImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """深度爬取网站并批量导入为链接文档"""
    discovered_urls, document_ids = await crawl_and_import(
        db=db,
        space_id=space_id,
        user_id=current_user.id,
        url=str(data.url),
        max_pages=data.max_pages,
        url_pattern=data.url_pattern,
    )
    return CrawlImportResponse(
        discovered_urls=discovered_urls,
        document_ids=document_ids,
        total=len(document_ids),
    )


@router.delete("/{space_id}/documents/{document_id}")
async def remove_document(
    space_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除文档或链接"""
    await delete_document(
        db=db,
        space_id=space_id,
        document_id=document_id,
        user_id=current_user.id,
    )
    return {"message": "删除成功"}
