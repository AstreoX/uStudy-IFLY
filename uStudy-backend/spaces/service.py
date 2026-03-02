"""学习空间业务逻辑"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_settings
from db.models import DocumentType, Edge, Node, ReviewSchedule, Space, SpaceDocument, StudyActivityLog
from spaces.schemas import (
    EdgeResponse,
    NodeResponse,
    SpaceCreate,
    SpaceGraphResponse,
    SpaceResponse,
    SpaceUpdate,
)

logger = logging.getLogger(__name__)


class SpaceNotFoundError(Exception):
    """学习空间不存在"""

    pass


class SpaceAccessDeniedError(Exception):
    """无权访问学习空间"""

    pass


class SpaceService:
    """学习空间服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_space(self, user_id: UUID, request: SpaceCreate) -> SpaceResponse:
        """创建学习空间"""
        # Build learning preferences dict with metadata if provided
        preferences_dict = None
        if request.learning_preferences:
            preferences_dict = request.learning_preferences.model_dump(exclude_none=True)
            if preferences_dict:
                preferences_dict["created_at"] = datetime.now(timezone.utc).isoformat()
                preferences_dict["source"] = "create_space_api"

        space = Space(
            user_id=user_id,
            name=request.name,
            description=request.description,
            color=request.color,
            learning_preferences=preferences_dict,
        )
        self.db.add(space)
        await self.db.commit()
        await self.db.refresh(space)
        return SpaceResponse.model_validate(space)

    async def get_user_spaces(self, user_id: UUID) -> List[SpaceResponse]:
        """获取用户所有学习空间"""
        stmt = (
            select(Space)
            .where(Space.user_id == user_id)
            .order_by(Space.updated_at.desc())
        )
        result = await self.db.execute(stmt)
        spaces = result.scalars().all()
        return [SpaceResponse.model_validate(s) for s in spaces]

    async def get_space(self, user_id: UUID, space_id: UUID) -> SpaceResponse:
        """获取单个学习空间"""
        space = await self._get_space_with_access_check(user_id, space_id)
        return SpaceResponse.model_validate(space)

    async def update_space(
        self, user_id: UUID, space_id: UUID, request: SpaceUpdate
    ) -> SpaceResponse:
        """更新学习空间"""
        space = await self._get_space_with_access_check(user_id, space_id)

        if request.name is not None:
            space.name = request.name
        if request.description is not None:
            space.description = request.description
        if request.color is not None:
            space.color = request.color

        await self.db.commit()
        await self.db.refresh(space)
        return SpaceResponse.model_validate(space)

    async def delete_space(self, user_id: UUID, space_id: UUID) -> None:
        """删除学习空间（含物理文件清理和级联删除）"""
        space = await self._get_space_with_access_check(user_id, space_id)

        # 先收集需要删除的文件路径（在删除数据库记录之前）
        file_paths = await self._collect_document_file_paths(space_id)

        # 删除该空间关联的复习计划（必须在空间删除前执行，
        # 因为空间删除会 SET NULL StudyActivityLog.space_id，之后无法关联）
        activity_ids_subquery = (
            select(StudyActivityLog.id)
            .where(StudyActivityLog.space_id == space_id)
            .scalar_subquery()
        )
        await self.db.execute(
            delete(ReviewSchedule).where(
                ReviewSchedule.activity_id.in_(activity_ids_subquery)
            )
        )

        # 删除数据库记录（级联删除 nodes, edges, conversations, documents 等）
        await self.db.delete(space)
        await self.db.commit()

        # 数据库删除成功后，清理物理文件（best effort）
        deleted_count = self._cleanup_files(file_paths)

        logger.info(
            f"Deleted space {space_id} for user {user_id}, cleaned {deleted_count} files"
        )

    async def _collect_document_file_paths(self, space_id: UUID) -> list[Path]:
        """收集空间下所有文档的物理文件路径（在删除数据库记录前调用）"""
        settings = get_settings()

        # 查询该空间下所有 DOCUMENT 类型的记录
        stmt = select(SpaceDocument).where(
            SpaceDocument.space_id == space_id,
            SpaceDocument.doc_type == DocumentType.DOCUMENT,
        )
        result = await self.db.execute(stmt)
        documents = result.scalars().all()

        if not documents:
            return []

        uploads_dir = Path(settings.upload_dir).resolve()
        file_paths: list[Path] = []

        for doc in documents:
            if not doc.url:
                continue

            # 提取相对路径并构建完整文件路径
            relative_path = doc.url.lstrip("/uploads/")
            file_path = (uploads_dir / relative_path).resolve()

            # 安全验证：确保文件路径在 uploads 目录内（防止路径遍历攻击）
            if not file_path.is_relative_to(uploads_dir):
                logger.warning(f"Skipping file outside uploads dir: {file_path}")
                continue

            file_paths.append(file_path)

        return file_paths

    def _cleanup_files(self, file_paths: list[Path]) -> int:
        """删除物理文件（best effort，不抛异常）"""
        deleted_count = 0

        for file_path in file_paths:
            if not file_path.exists():
                continue

            try:
                os.remove(file_path)
                logger.info(f"Deleted document file: {file_path}")
                deleted_count += 1
            except OSError as e:
                logger.warning(f"Failed to delete orphaned file {file_path}: {e}")

        return deleted_count

    async def get_space_graph(
        self, user_id: UUID, space_id: UUID
    ) -> SpaceGraphResponse:
        """获取学习空间的知识图谱（节点和边）"""
        # 验证访问权限
        await self._get_space_with_access_check(user_id, space_id)

        # 查询节点
        nodes_stmt = select(Node).where(Node.space_id == space_id)
        nodes_result = await self.db.execute(nodes_stmt)
        nodes = nodes_result.scalars().all()

        # 查询边
        edges_stmt = select(Edge).where(Edge.space_id == space_id)
        edges_result = await self.db.execute(edges_stmt)
        edges = edges_result.scalars().all()

        return SpaceGraphResponse(
            nodes=[NodeResponse.model_validate(n) for n in nodes],
            edges=[
                EdgeResponse(
                    id=e.id,
                    from_node_id=e.from_node_id,
                    to_node_id=e.to_node_id,
                    type=e.type.value,
                )
                for e in edges
            ],
        )

    async def _get_space_with_access_check(self, user_id: UUID, space_id: UUID) -> Space:
        """获取空间并验证访问权限"""
        stmt = select(Space).where(Space.id == space_id)
        result = await self.db.execute(stmt)
        space = result.scalar_one_or_none()

        if not space:
            raise SpaceNotFoundError(f"Space {space_id} not found")

        if space.user_id != user_id:
            raise SpaceAccessDeniedError(f"Access denied to space {space_id}")

        return space
