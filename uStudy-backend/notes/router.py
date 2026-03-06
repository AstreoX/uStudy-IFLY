"""笔记模块 API 端点"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from notes.exceptions import NoteAccessDeniedError, NoteNotFoundError
from notes.schemas import (
    AddLinkRequest,
    NoteAttachmentResponse,
    NoteCreate,
    NoteListItem,
    NoteResponse,
    NoteUpdate,
)
from notes.service import MAX_FILE_SIZE, NoteService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/spaces/{space_id}/notes", tags=["notes"])


def _handle_note_error(e: Exception) -> None:
    if isinstance(e, NoteNotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, NoteAccessDeniedError):
        raise HTTPException(status_code=403, detail=str(e))
    logger.error("笔记操作失败: %s", e, exc_info=True)
    raise HTTPException(status_code=500, detail="操作失败，请稍后重试")


@router.post("/", response_model=NoteResponse, status_code=201)
async def create_note(
    space_id: UUID,
    request: NoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteResponse:
    """创建笔记"""
    try:
        service = NoteService(db)
        return await service.create_note(current_user.id, space_id, request)
    except (NoteNotFoundError, NoteAccessDeniedError) as e:
        _handle_note_error(e)


@router.get("/", response_model=list[NoteListItem])
async def list_notes(
    space_id: UUID,
    node_id: Optional[UUID] = Query(None, description="筛选某节点的笔记"),
    free_only: bool = Query(False, description="仅返回自由笔记"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[NoteListItem]:
    """列出空间笔记"""
    try:
        service = NoteService(db)
        return await service.list_notes(current_user.id, space_id, node_id, free_only)
    except (NoteNotFoundError, NoteAccessDeniedError) as e:
        _handle_note_error(e)


@router.get("/{note_id}", response_model=NoteResponse)
async def get_note(
    space_id: UUID,
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteResponse:
    """获取单条笔记（含附件）"""
    try:
        service = NoteService(db)
        return await service.get_note(current_user.id, space_id, note_id)
    except (NoteNotFoundError, NoteAccessDeniedError) as e:
        _handle_note_error(e)


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    space_id: UUID,
    note_id: UUID,
    request: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteResponse:
    """更新笔记"""
    try:
        service = NoteService(db)
        return await service.update_note(current_user.id, space_id, note_id, request)
    except (NoteNotFoundError, NoteAccessDeniedError) as e:
        _handle_note_error(e)


@router.delete("/{note_id}", status_code=204)
async def delete_note(
    space_id: UUID,
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """删除笔记（级联删除附件文件）"""
    try:
        service = NoteService(db)
        await service.delete_note(current_user.id, space_id, note_id)
    except (NoteNotFoundError, NoteAccessDeniedError) as e:
        _handle_note_error(e)


@router.post(
    "/{note_id}/attachments/upload",
    response_model=NoteAttachmentResponse,
    status_code=201,
)
async def upload_attachment(
    space_id: UUID,
    note_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteAttachmentResponse:
    """上传附件文件（图片或文档）"""
    try:
        service = NoteService(db)

        chunks = []
        total = 0
        while True:
            chunk = await file.read(8192)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"文件大小超过限制 (最大 {MAX_FILE_SIZE // 1024 // 1024}MB)",
                )
            chunks.append(chunk)

        file_data = b"".join(chunks)
        original_filename = file.filename or "unnamed"
        mime_type = file.content_type or "application/octet-stream"

        return await service.add_attachment(
            current_user.id, space_id, note_id, file_data, original_filename, mime_type
        )
    except (NoteNotFoundError, NoteAccessDeniedError) as e:
        _handle_note_error(e)


@router.post(
    "/{note_id}/attachments/link",
    response_model=NoteAttachmentResponse,
    status_code=201,
)
async def add_link(
    space_id: UUID,
    note_id: UUID,
    request: AddLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteAttachmentResponse:
    """添加链接附件"""
    try:
        service = NoteService(db)
        return await service.add_link(
            current_user.id, space_id, note_id, request
        )
    except (NoteNotFoundError, NoteAccessDeniedError) as e:
        _handle_note_error(e)


@router.delete("/{note_id}/attachments/{attachment_id}", status_code=204)
async def delete_attachment(
    space_id: UUID,
    note_id: UUID,
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """删除单个附件"""
    try:
        service = NoteService(db)
        await service.delete_attachment(
            current_user.id, space_id, note_id, attachment_id
        )
    except (NoteNotFoundError, NoteAccessDeniedError) as e:
        _handle_note_error(e)
