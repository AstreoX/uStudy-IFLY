"""文件夹模块 API 端点"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import FolderContentType, User
from folders.schemas import (
    FolderCreate,
    FolderResponse,
    FolderUpdate,
    MoveItemsRequest,
    MoveFolderRequest,
)
from folders.service import (
    FolderAccessDeniedError,
    FolderCyclicError,
    FolderDepthExceededError,
    FolderNotFoundError,
    FolderService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/spaces/{space_id}/folders", tags=["folders"])


def _handle_folder_error(e: Exception) -> None:
    if isinstance(e, FolderNotFoundError):
        raise HTTPException(status_code=404, detail=str(e))
    if isinstance(e, FolderAccessDeniedError):
        raise HTTPException(status_code=403, detail=str(e))
    if isinstance(e, (FolderDepthExceededError, FolderCyclicError)):
        raise HTTPException(status_code=400, detail=str(e))
    logger.error("文件夹操作失败: %s", e, exc_info=True)
    raise HTTPException(status_code=500, detail="操作失败，请稍后重试")


@router.post("", response_model=FolderResponse, status_code=201)
async def create_folder(
    space_id: UUID,
    request: FolderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FolderResponse:
    """创建文件夹"""
    try:
        service = FolderService(db)
        return await service.create_folder(current_user.id, space_id, request)
    except (
        FolderNotFoundError,
        FolderAccessDeniedError,
        FolderDepthExceededError,
    ) as e:
        _handle_folder_error(e)


@router.get("", response_model=list[FolderResponse])
async def list_folders(
    space_id: UUID,
    content_type: FolderContentType = Query(..., description="内容类型: notes 或 quizzes"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FolderResponse]:
    """列出空间内指定类型的所有文件夹"""
    try:
        service = FolderService(db)
        return await service.list_folders(current_user.id, space_id, content_type)
    except (FolderNotFoundError, FolderAccessDeniedError) as e:
        _handle_folder_error(e)


@router.patch("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    space_id: UUID,
    folder_id: UUID,
    request: FolderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FolderResponse:
    """重命名文件夹"""
    try:
        service = FolderService(db)
        return await service.update_folder(
            current_user.id, space_id, folder_id, request
        )
    except (FolderNotFoundError, FolderAccessDeniedError) as e:
        _handle_folder_error(e)


@router.delete("/{folder_id}", status_code=204)
async def delete_folder(
    space_id: UUID,
    folder_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """删除文件夹（级联删除子文件夹，内容变为未分类）"""
    try:
        service = FolderService(db)
        await service.delete_folder(current_user.id, space_id, folder_id)
    except (FolderNotFoundError, FolderAccessDeniedError) as e:
        _handle_folder_error(e)


@router.post("/{folder_id}/move", response_model=FolderResponse)
async def move_folder(
    space_id: UUID,
    folder_id: UUID,
    request: MoveFolderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FolderResponse:
    """移动文件夹到新的父文件夹（null = 移至根目录）"""
    try:
        service = FolderService(db)
        return await service.move_folder(
            current_user.id, space_id, folder_id, request.target_parent_id
        )
    except (
        FolderNotFoundError,
        FolderAccessDeniedError,
        FolderDepthExceededError,
        FolderCyclicError,
    ) as e:
        _handle_folder_error(e)


@router.post("/move-notes")
async def move_notes(
    space_id: UUID,
    request: MoveItemsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """批量移动笔记到文件夹（target_folder_id=null 移至根目录）"""
    try:
        service = FolderService(db)
        count = await service.move_notes(current_user.id, space_id, request)
        return {"moved": count}
    except (FolderNotFoundError, FolderAccessDeniedError) as e:
        _handle_folder_error(e)


@router.post("/move-quizzes")
async def move_quizzes(
    space_id: UUID,
    request: MoveItemsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """批量移动测试到文件夹（target_folder_id=null 移至根目录）"""
    try:
        service = FolderService(db)
        count = await service.move_quizzes(current_user.id, space_id, request)
        return {"moved": count}
    except (FolderNotFoundError, FolderAccessDeniedError) as e:
        _handle_folder_error(e)
