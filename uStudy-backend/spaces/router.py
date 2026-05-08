"""学习空间 API 路由"""

from typing import List
from uuid import UUID

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from chat.tools.catalog import get_catalog_for_api
from db.database import get_db
from db.models import LearningPathEvent, User
from spaces.schemas import (
    LearningPathEventResponse,
    SpaceCreate,
    SpaceGraphResponse,
    SpaceResponse,
    SpaceUpdate,
)
from quota.service import check_space_count_quota
from spaces.service import SpaceAccessDeniedError, SpaceNotFoundError, SpaceService

router = APIRouter(
    prefix="/api/spaces",
    tags=["spaces"],
)


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
    await check_space_count_quota(db, user)
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
    "/tool-catalog",
    summary="获取工具目录",
)
async def get_tool_catalog(
    user: User = Depends(get_current_user),
) -> list[dict]:
    """返回按分类组织的工具目录（供前端手动模式 UI 展示）"""
    return get_catalog_for_api()


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
    target_user_id: UUID | None = Query(None, description="目标用户ID（协作空间中查看其他成员的掌握度）"),
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
        return await service.get_space_graph(user.id, space_id, target_user_id=target_user_id)
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
    "/{space_id}/members",
    summary="获取协作空间成员列表",
)
async def get_space_members(
    space_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """获取协作空间的所有成员（含角色、昵称、头像）"""
    service = SpaceService(db)
    try:
        return await service.get_space_members(user.id, space_id)
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
    "/{space_id}/members/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="移除成员或退出空间",
)
async def remove_space_member(
    space_id: UUID,
    target_user_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Owner 移除成员，或成员自行退出（target_user_id == self）"""
    service = SpaceService(db)
    try:
        await service.remove_member(user.id, space_id, target_user_id)
    except SpaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MEMBER_NOT_FOUND", "message": "成员不存在"},
        )
    except SpaceAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SPACE_ACCESS_DENIED", "message": str(e)},
        )


class UpdateMemberPermissionRequest(BaseModel):
    can_edit_graph: bool | None = None


@router.patch("/{space_id}/members/{target_user_id}", summary="更新成员权限")
async def update_member_permission(
    space_id: UUID,
    target_user_id: UUID,
    request: UpdateMemberPermissionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = SpaceService(db)
    try:
        return await service.update_member_permission(
            user.id, space_id, target_user_id, can_edit_graph=request.can_edit_graph
        )
    except SpaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "MEMBER_NOT_FOUND", "message": "成员不存在"},
        )
    except SpaceAccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SPACE_ACCESS_DENIED", "message": str(e)},
        )


@router.get(
    "/{space_id}/path-events",
    response_model=list[LearningPathEventResponse],
    summary="获取学习路径扩展事件",
)
async def get_learning_path_events(
    space_id: UUID,
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LearningPathEventResponse]:
    """获取该空间的学习路径扩展事件历史"""
    # Validate space ownership
    service = SpaceService(db)
    try:
        await service.get_space(user.id, space_id)
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

    result = await db.execute(
        select(LearningPathEvent)
        .where(LearningPathEvent.space_id == space_id)
        .order_by(LearningPathEvent.created_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    return [LearningPathEventResponse.model_validate(e) for e in events]
