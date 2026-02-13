"""学习空间 API 路由"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from spaces.schemas import (
    SpaceCreate,
    SpaceGraphResponse,
    SpaceResponse,
    SpaceUpdate,
)
from spaces.service import SpaceAccessDeniedError, SpaceNotFoundError, SpaceService

router = APIRouter(prefix="/api/spaces", tags=["spaces"])


@router.post(
    "",
    response_model=SpaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建学习空间",
)
async def create_space(
    request: SpaceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpaceResponse:
    """
    创建新的学习空间

    - **name**: 学习主题名称
    - **description**: 描述（可选）
    - **color**: 十六进制颜色（如 #0F6FFF）
    """
    service = SpaceService(db)
    return await service.create_space(user.id, request)


@router.get(
    "",
    response_model=List[SpaceResponse],
    summary="获取用户所有学习空间",
)
async def get_spaces(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SpaceResponse]:
    """获取当前用户的所有学习空间，按更新时间倒序"""
    service = SpaceService(db)
    return await service.get_user_spaces(user.id)


@router.get(
    "/{space_id}",
    response_model=SpaceResponse,
    summary="获取单个学习空间",
)
async def get_space(
    space_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpaceResponse:
    """获取指定学习空间的详情"""
    service = SpaceService(db)
    try:
        return await service.get_space(user.id, space_id)
    except SpaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SPACE_NOT_FOUND", "message": "学习空间不存在"},
        )
    except SpaceAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SPACE_ACCESS_DENIED", "message": "无权访问该学习空间"},
        )


@router.patch(
    "/{space_id}",
    response_model=SpaceResponse,
    summary="更新学习空间",
)
async def update_space(
    space_id: UUID,
    request: SpaceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpaceResponse:
    """更新学习空间信息"""
    service = SpaceService(db)
    try:
        return await service.update_space(user.id, space_id, request)
    except SpaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SPACE_NOT_FOUND", "message": "学习空间不存在"},
        )
    except SpaceAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SPACE_ACCESS_DENIED", "message": "无权访问该学习空间"},
        )


@router.delete(
    "/{space_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除学习空间",
)
async def delete_space(
    space_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除学习空间（会级联删除所有节点和边）"""
    service = SpaceService(db)
    try:
        await service.delete_space(user.id, space_id)
    except SpaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SPACE_NOT_FOUND", "message": "学习空间不存在"},
        )
    except SpaceAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SPACE_ACCESS_DENIED", "message": "无权访问该学习空间"},
        )


@router.get(
    "/{space_id}/graph",
    response_model=SpaceGraphResponse,
    summary="获取知识图谱",
)
async def get_space_graph(
    space_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SpaceGraphResponse:
    """
    获取学习空间的知识图谱

    返回所有节点和边，边包含类型：
    - **knowledge_tree**: 知识树边（主体结构）
    - **learning_path**: 学习路径边
    - **advanced**: 进阶关联边
    """
    service = SpaceService(db)
    try:
        return await service.get_space_graph(user.id, space_id)
    except SpaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SPACE_NOT_FOUND", "message": "学习空间不存在"},
        )
    except SpaceAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SPACE_ACCESS_DENIED", "message": "无权访问该学习空间"},
        )
