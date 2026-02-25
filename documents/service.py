"""Business logic for documents module."""

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.models import DocumentType, Space, SpaceDocument, User
from quota.service import check_storage_quota

settings = get_settings()
logger = logging.getLogger(__name__)

# 保存后台任务的引用，防止被 GC
_background_tasks: set[asyncio.Task] = set()


async def verify_space_ownership(
    db: AsyncSession, space_id: uuid.UUID, user_id: uuid.UUID
) -> Space:
    """验证用户是否拥有该学习空间"""
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()

    if not space:
        raise HTTPException(status_code=404, detail="学习空间不存在")

    if space.user_id != user_id:
        raise HTTPException(status_code=403, detail="无权访问该学习空间")

    return space


async def create_link(
    db: AsyncSession,
    space_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    url: str,
) -> SpaceDocument:
    """创建链接"""
    await verify_space_ownership(db, space_id, user_id)

    document = SpaceDocument(
        space_id=space_id,
        doc_type=DocumentType.LINK,
        title=title,
        url=str(url),
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)

    return document


async def upload_document(
    db: AsyncSession,
    space_id: uuid.UUID,
    user_id: uuid.UUID,
    file: UploadFile,
    user: User | None = None,
) -> SpaceDocument:
    """上传文档"""
    await verify_space_ownership(db, space_id, user_id)

    # 验证文件类型
    if file.content_type not in settings.document_allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file.content_type}。支持的类型: PDF, Word, TXT",
        )

    # 验证文件扩展名
    original_filename = file.filename or "untitled"
    file_ext = Path(original_filename).suffix.lower()
    if file_ext not in settings.document_allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件扩展名: {file_ext}。支持的扩展名: {', '.join(settings.document_allowed_extensions)}",
        )

    # 读取文件内容
    content = await file.read()

    # Storage quota check
    if user is not None:
        await check_storage_quota(db, user, space_id, len(content))

    # 验证文件大小
    if len(content) > settings.document_max_size_bytes:
        max_mb = settings.document_max_size_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=400, detail=f"文件大小超过限制（最大 {max_mb}MB）"
        )

    # 生成存储路径
    documents_dir = Path(settings.upload_dir) / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)

    # 生成唯一文件名
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = documents_dir / unique_filename

    try:
        # 保存文件
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        # 生成可访问的 URL
        file_url = f"/uploads/documents/{unique_filename}"

        # 创建数据库记录
        document = SpaceDocument(
            space_id=space_id,
            doc_type=DocumentType.DOCUMENT,
            title=Path(original_filename).stem,  # 使用不含扩展名的文件名作为标题
            url=file_url,
            original_filename=original_filename,
            file_size=len(content),
            mime_type=file.content_type,
        )

        db.add(document)
        await db.commit()
        await db.refresh(document)

        # 自动触发 RAG 处理（后台异步执行）
        schedule_document_processing(document.id)

        return document
    except Exception:
        # 数据库操作失败时清理已上传的文件
        if file_path.exists():
            os.remove(file_path)
        raise


async def get_space_documents(
    db: AsyncSession,
    space_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[SpaceDocument]:
    """获取学习空间的所有文档和链接"""
    await verify_space_ownership(db, space_id, user_id)

    result = await db.execute(
        select(SpaceDocument)
        .where(SpaceDocument.space_id == space_id)
        .order_by(SpaceDocument.created_at.desc())
    )

    return list(result.scalars().all())


async def delete_document(
    db: AsyncSession,
    space_id: uuid.UUID,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """删除文档或链接"""
    await verify_space_ownership(db, space_id, user_id)

    result = await db.execute(
        select(SpaceDocument).where(
            SpaceDocument.id == document_id, SpaceDocument.space_id == space_id
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 保存文件路径信息用于后续删除
    file_to_delete = None
    if document.doc_type == DocumentType.DOCUMENT and document.url:
        # 安全路径验证：防止路径遍历攻击
        relative_path = document.url.lstrip("/uploads/")
        file_path = (Path(settings.upload_dir) / relative_path).resolve()
        uploads_dir = Path(settings.upload_dir).resolve()

        # 确保文件路径在 uploads 目录内
        if file_path.is_relative_to(uploads_dir) and file_path.exists():
            file_to_delete = file_path

    # 先删除数据库记录
    await db.delete(document)
    await db.commit()

    # 数据库操作成功后再删除文件
    if file_to_delete:
        os.remove(file_to_delete)


async def get_document_by_id(
    db: AsyncSession,
    document_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Optional[SpaceDocument]:
    """根据 ID 获取文档（验证权限）"""
    result = await db.execute(
        select(SpaceDocument)
        .join(Space, SpaceDocument.space_id == Space.id)
        .where(SpaceDocument.id == document_id, Space.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def trigger_document_processing(document_id: uuid.UUID) -> None:
    """
    触发文档 RAG 处理（后台任务）

    在独立的数据库会话中运行，不阻塞请求。
    """
    from db.database import AsyncSessionLocal
    from rag.service import DocumentProcessingService

    async with AsyncSessionLocal() as db:
        try:
            service = DocumentProcessingService(db)
            await service.process_document(document_id)
        except Exception as e:
            logger.error("文档处理失败: %s - %s", document_id, str(e), exc_info=True)
            # 不抛出异常，避免影响后台任务


def schedule_document_processing(document_id: uuid.UUID) -> None:
    """
    调度文档处理任务

    使用 asyncio.create_task 在后台运行，不阻塞当前请求。
    任务引用保存在 _background_tasks 集合中，防止被 GC 回收。
    """
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(trigger_document_processing(document_id))
        # 保存任务引用，防止被 GC 回收
        _background_tasks.add(task)
        # 任务完成后自动从集合中移除
        task.add_done_callback(_background_tasks.discard)
        logger.info("已调度文档处理任务: %s", document_id)
    except RuntimeError:
        # 没有运行中的事件循环
        logger.warning("无法调度文档处理任务：没有运行中的事件循环")
