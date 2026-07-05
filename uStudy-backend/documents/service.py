"""Business logic for documents module."""

import asyncio
import logging
import os
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.models import DocumentType, Space, SpaceDocument, User
from quota.service import check_storage_quota
from rag.parsing import (
    DocumentFormatError,
    get_supported_document_extensions,
    resolve_document_format_from_path,
)

settings = get_settings()
logger = logging.getLogger(__name__)

# 保存后台任务的引用，防止被 GC
_background_tasks: set[asyncio.Task] = set()
UPLOAD_STREAM_CHUNK_SIZE = 1024 * 1024


async def verify_space_ownership(
    db: AsyncSession, space_id: uuid.UUID, user_id: uuid.UUID
) -> Space:
    """验证用户是否有权访问该学习空间（owner 或 member）"""
    from spaces.authorization import SpaceAccessDeniedError, SpaceNotFoundError
    from spaces.authorization import verify_space_access as _verify

    try:
        return await _verify(db, space_id, user_id)
    except SpaceNotFoundError:
        raise HTTPException(status_code=404, detail="学习空间不存在")
    except SpaceAccessDeniedError:
        raise HTTPException(status_code=403, detail="无权访问该学习空间")


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

    # Trigger async RAG processing (same as file upload)
    schedule_document_processing(document.id)

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
    original_filename = file.filename or "untitled"

    # 确定单文件大小限制（按用户等级）
    if user is not None:
        from quota.service import get_user_tier_limits

        limits = get_user_tier_limits(user)
        max_file_bytes = limits.max_upload_file_bytes
    else:
        max_file_bytes = settings.document_max_size_bytes
    max_size_error = _build_file_size_limit_message(max_file_bytes, user)

    temp_dir = Path(settings.upload_dir) / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{uuid.uuid4()}.upload"
    file_path: Path | None = None

    try:
        file_size = await _stream_upload_to_temp_file(
            file=file,
            destination=temp_path,
            max_file_bytes=max_file_bytes,
            max_size_error=max_size_error,
        )

        # Storage quota check
        if user is not None:
            await check_storage_quota(db, user, space_id, file_size)

        try:
            resolved_format = await asyncio.to_thread(
                resolve_document_format_from_path,
                temp_path,
                original_filename,
                file.content_type,
            )
        except DocumentFormatError as exc:
            supported_extensions = ", ".join(get_supported_document_extensions())
            raise HTTPException(
                status_code=400,
                detail=f"{exc}。支持的扩展名: {supported_extensions}",
            ) from exc

        # 生成存储路径
        documents_dir = Path(settings.upload_dir) / "documents"
        documents_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名
        storage_ext = Path(original_filename).suffix.lower() or resolved_format.storage_extension
        unique_filename = f"{uuid.uuid4()}{storage_ext}"
        file_path = documents_dir / unique_filename

        await asyncio.to_thread(os.replace, temp_path, file_path)

        # 生成可访问的 URL
        file_url = f"/uploads/documents/{unique_filename}"

        # 创建数据库记录
        document = SpaceDocument(
            space_id=space_id,
            doc_type=DocumentType.DOCUMENT,
            title=Path(original_filename).stem,  # 使用不含扩展名的文件名作为标题
            url=file_url,
            original_filename=original_filename,
            file_size=file_size,
            mime_type=resolved_format.mime_type,
        )

        db.add(document)
        await db.commit()
        await db.refresh(document)

        # 自动触发 RAG 处理（后台异步执行）
        schedule_document_processing(document.id)

        return document
    except Exception:
        # 数据库操作失败时清理已上传的文件
        if file_path and file_path.exists():
            os.remove(file_path)
        if temp_path.exists():
            os.remove(temp_path)
        raise
    finally:
        with suppress(Exception):
            await file.close()


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


def _build_file_size_limit_message(max_file_bytes: int, user: User | None) -> str:
    max_mb = max(1, (max_file_bytes + 1024 * 1024 - 1) // (1024 * 1024))
    tier = None
    if user is not None:
        from quota.service import get_effective_tier

        tier = get_effective_tier(user)

    tier_names = {
        "FREE": "免费版",
        "BASIC": "Plus",
        "PREMIUM": "Premium",
        "ALPHA": "Alpha",
        "ULTRA": "Ultra",
    }
    tier_label = tier_names.get(tier.value, "") if tier else ""
    msg = f"文件大小超过当前{tier_label}等级限制（最大 {max_mb}MB）"
    if tier and tier.value in ("FREE", "BASIC"):
        msg += "，升级订阅可获得更大的上传额度"
    return msg


async def _stream_upload_to_temp_file(
    *,
    file: UploadFile,
    destination: Path,
    max_file_bytes: int,
    max_size_error: str,
) -> int:
    total = 0

    async with aiofiles.open(destination, "wb") as handle:
        while True:
            chunk = await file.read(UPLOAD_STREAM_CHUNK_SIZE)
            if not chunk:
                break

            total += len(chunk)
            if total > max_file_bytes:
                raise HTTPException(status_code=400, detail=max_size_error)

            await handle.write(chunk)

    return total
