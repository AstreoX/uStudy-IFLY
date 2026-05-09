"""学习空间业务逻辑"""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from uuid import UUID

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_settings
from db.models import (
    DocumentType,
    Edge,
    Node,
    ReviewSchedule,
    Space,
    SpaceDocument,
    SpaceMember,
    SpaceMemberRole,
    StudyActivityLog,
)
from spaces.authorization import (
    SpaceAccessDeniedError,
    SpaceNotFoundError,
    get_user_role_in_space,
    verify_space_access,
    verify_space_ownership,
)
from spaces.schemas import (
    EdgeResponse,
    NodeResponse,
    SpaceCreate,
    SpaceGraphResponse,
    SpaceResponse,
    SpaceUpdate,
)

logger = logging.getLogger(__name__)

# Re-export for backward compatibility with other modules that import from here
__all__ = ["SpaceService", "SpaceNotFoundError", "SpaceAccessDeniedError"]


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
        await self.db.flush()

        # Seed space_members with OWNER row
        from spaces.colors import get_next_color

        owner_member = SpaceMember(
            space_id=space.id,
            user_id=user_id,
            role=SpaceMemberRole.OWNER,
            color=get_next_color(0),
        )
        self.db.add(owner_member)

        await self.db.commit()
        await self.db.refresh(space)
        return self._to_response(space, user_role="owner")

    async def get_user_spaces(self, user_id: UUID) -> List[SpaceResponse]:
        """获取用户所有学习空间 (owned + member)"""
        # Join via space_members to get both owned and joined spaces
        stmt = (
            select(Space, SpaceMember.role)
            .join(SpaceMember, SpaceMember.space_id == Space.id)
            .where(SpaceMember.user_id == user_id)
            .order_by(Space.updated_at.desc())
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        responses = []
        for space, role in rows:
            responses.append(self._to_response(space, user_role=role.value))
        return responses

    async def get_space(self, user_id: UUID, space_id: UUID) -> SpaceResponse:
        """获取单个学习空间"""
        space = await verify_space_access(self.db, space_id, user_id)
        user_role = await get_user_role_in_space(self.db, space_id, user_id)
        return self._to_response(space, user_role=user_role)

    async def update_space(
        self, user_id: UUID, space_id: UUID, request: SpaceUpdate
    ) -> SpaceResponse:
        """更新学习空间"""
        space = await verify_space_access(self.db, space_id, user_id)

        if request.name is not None:
            space.name = request.name
        if request.description is not None:
            space.description = request.description
        if request.color is not None:
            space.color = request.color

        await self.db.commit()
        await self.db.refresh(space)
        user_role = await get_user_role_in_space(self.db, space_id, user_id)
        return self._to_response(space, user_role=user_role)

    async def delete_space(self, user_id: UUID, space_id: UUID) -> None:
        """删除学习空间 — owner 删除空间，member 退出空间"""
        space = await verify_space_access(self.db, space_id, user_id)

        if space.user_id != user_id:
            # Non-owner member: leave instead of delete
            await self.remove_member(user_id, space_id, user_id)
            return

        # 先收集需要删除的文件路径（在删除数据库记录之前）
        file_paths = await self._collect_document_file_paths(space_id)

        # 删除该空间关联的复习计划
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

        # 删除数据库记录（级联删除 nodes, edges, conversations, documents, members 等）
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

            relative_path = doc.url.lstrip("/uploads/")
            file_path = (uploads_dir / relative_path).resolve()

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
        self, user_id: UUID, space_id: UUID, target_user_id: UUID | None = None
    ) -> SpaceGraphResponse:
        """获取学习空间的知识图谱（节点和边）"""
        space = await verify_space_access(self.db, space_id, user_id)

        if space.is_collaborative:
            effective_user_id = target_user_id or user_id
            # Use GraphService with per-user mastery
            from graph.service import GraphService

            graph_service = GraphService(self.db)
            graph_data = await graph_service.get_graph(
                space_id, user_id=effective_user_id, is_collaborative=True
            )
            return SpaceGraphResponse(
                nodes=[
                    NodeResponse(
                        id=UUID(n["id"]),
                        label=n["label"],
                        mastery=n["mastery"],
                    )
                    for n in graph_data["nodes"]
                ],
                edges=[
                    EdgeResponse(
                        id=UUID(e["id"]),
                        from_node_id=UUID(e["from_node_id"]),
                        to_node_id=UUID(e["to_node_id"]),
                        type=e["type"],
                        user_id=UUID(e["user_id"]) if e.get("user_id") else None,
                    )
                    for e in graph_data["edges"]
                ],
            )

        # Non-collaborative: existing behavior
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

    # ---- Membership ----

    async def get_space_members(self, user_id: UUID, space_id: UUID) -> list[dict]:
        """获取协作空间的成员列表"""
        await verify_space_access(self.db, space_id, user_id)

        from db.models import User

        stmt = (
            select(SpaceMember, User.nickname, User.avatar_url)
            .join(User, User.id == SpaceMember.user_id)
            .where(SpaceMember.space_id == space_id)
            .order_by(SpaceMember.joined_at)
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            {
                "user_id": str(member.user_id),
                "role": member.role.value,
                "nickname": nickname,
                "avatar_url": avatar_url,
                "joined_at": member.joined_at.isoformat(),
                "color": member.color,
                "can_edit_graph": member.can_edit_graph,
            }
            for member, nickname, avatar_url in rows
        ]

    async def remove_member(
        self, requesting_user_id: UUID, space_id: UUID, target_user_id: UUID
    ) -> None:
        """移除成员 (owner removes member, or member leaves)"""
        space = await verify_space_access(self.db, space_id, requesting_user_id)
        is_owner = space.user_id == requesting_user_id
        is_self_leaving = requesting_user_id == target_user_id

        if not is_owner and not is_self_leaving:
            raise SpaceAccessDeniedError("只有空间所有者可以移除其他成员")

        # Cannot remove the owner
        if target_user_id == space.user_id:
            raise SpaceAccessDeniedError("无法移除空间所有者")

        result = await self.db.execute(
            select(SpaceMember).where(
                SpaceMember.space_id == space_id,
                SpaceMember.user_id == target_user_id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            raise SpaceNotFoundError("该用户不是此空间的成员")

        await self.db.delete(member)
        await self.db.commit()

    async def update_member_permission(
        self, requesting_user_id: UUID, space_id: UUID, target_user_id: UUID,
        can_edit_graph: bool | None = None,
    ) -> dict:
        """Owner updates member permissions."""
        space = await verify_space_access(self.db, space_id, requesting_user_id)
        if space.user_id != requesting_user_id:
            raise SpaceAccessDeniedError("只有空间所有者可以修改成员权限")
        if target_user_id == space.user_id:
            raise SpaceAccessDeniedError("无法修改所有者自身的权限")

        member = (await self.db.execute(
            select(SpaceMember).where(
                SpaceMember.space_id == space_id,
                SpaceMember.user_id == target_user_id,
            )
        )).scalar_one_or_none()
        if not member:
            raise SpaceNotFoundError("该用户不是此空间的成员")

        if can_edit_graph is not None:
            member.can_edit_graph = can_edit_graph
        await self.db.commit()
        await self.db.refresh(member)
        return {"user_id": str(member.user_id), "can_edit_graph": member.can_edit_graph}

    async def get_space_leaderboard(self, user_id: UUID, space_id: UUID) -> list[dict]:
        """获取协作空间排行榜数据"""
        await verify_space_access(self.db, space_id, user_id)

        from db.models import NodeUserMastery, Note, Quiz, QuizAttempt, User

        # 1) Get members
        stmt = (
            select(SpaceMember, User.nickname, User.avatar_url)
            .join(User, User.id == SpaceMember.user_id)
            .where(SpaceMember.space_id == space_id)
            .order_by(SpaceMember.joined_at)
        )
        result = await self.db.execute(stmt)
        members = result.all()

        if not members:
            return []

        member_ids = [m.user_id for m, _, _ in members]

        # 2) Average mastery + mastered count per user
        mastery_stmt = (
            select(
                NodeUserMastery.user_id,
                func.avg(NodeUserMastery.mastery).label("avg_mastery"),
                func.count(case((NodeUserMastery.mastery >= 80, 1))).label("mastered_count"),
            )
            .join(Node, Node.id == NodeUserMastery.node_id)
            .where(Node.space_id == space_id, NodeUserMastery.user_id.in_(member_ids))
            .group_by(NodeUserMastery.user_id)
        )
        mastery_result = await self.db.execute(mastery_stmt)
        mastery_map = {
            row.user_id: {"avg_mastery": round(float(row.avg_mastery), 1), "mastered_count": row.mastered_count}
            for row in mastery_result
        }

        # 3) Total nodes in space
        total_nodes = (await self.db.execute(
            select(func.count(Node.id)).where(Node.space_id == space_id)
        )).scalar() or 0

        # 4) Quiz scores per user
        quiz_stmt = (
            select(
                QuizAttempt.user_id,
                func.avg(QuizAttempt.score * 100.0 / func.nullif(QuizAttempt.total_score, 0)).label("avg_score"),
                func.count(QuizAttempt.id).label("quiz_count"),
            )
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(
                Quiz.space_id == space_id,
                QuizAttempt.user_id.in_(member_ids),
                QuizAttempt.status == "completed",
            )
            .group_by(QuizAttempt.user_id)
        )
        quiz_result = await self.db.execute(quiz_stmt)
        quiz_map = {
            row.user_id: {"avg_score": round(float(row.avg_score), 1) if row.avg_score else 0, "quiz_count": row.quiz_count}
            for row in quiz_result
        }

        # 5) Notes count per user
        notes_stmt = (
            select(Note.creator_user_id, func.count(Note.id).label("note_count"))
            .where(Note.space_id == space_id, Note.creator_user_id.in_(member_ids))
            .group_by(Note.creator_user_id)
        )
        notes_result = await self.db.execute(notes_stmt)
        notes_map = {row.creator_user_id: row.note_count for row in notes_result}

        # 6) Study activity count (last 30 days) per user
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        activity_stmt = (
            select(StudyActivityLog.user_id, func.count(StudyActivityLog.id).label("activity_count"))
            .where(
                StudyActivityLog.space_id == space_id,
                StudyActivityLog.user_id.in_(member_ids),
                StudyActivityLog.activity_time >= cutoff,
            )
            .group_by(StudyActivityLog.user_id)
        )
        activity_result = await self.db.execute(activity_stmt)
        activity_map = {row.user_id: row.activity_count for row in activity_result}

        # Build response, sorted by composite score
        leaderboard = []
        for member, nickname, avatar_url in members:
            uid = member.user_id
            m_data = mastery_map.get(uid, {"avg_mastery": 0, "mastered_count": 0})
            q_data = quiz_map.get(uid, {"avg_score": 0, "quiz_count": 0})
            notes_count = notes_map.get(uid, 0)
            activity_count = activity_map.get(uid, 0)

            # Composite: mastery 50% + quiz 30% + activity 20% (capped at 100)
            activity_score = min(activity_count * 2, 100)
            composite = round(
                m_data["avg_mastery"] * 0.5
                + q_data["avg_score"] * 0.3
                + activity_score * 0.2,
                1,
            )

            leaderboard.append({
                "user_id": str(uid),
                "nickname": nickname,
                "avatar_url": avatar_url,
                "color": member.color,
                "role": member.role.value,
                "avg_mastery": m_data["avg_mastery"],
                "mastered_nodes": m_data["mastered_count"],
                "total_nodes": total_nodes,
                "avg_quiz_score": q_data["avg_score"],
                "quiz_count": q_data["quiz_count"],
                "notes_count": notes_count,
                "activity_count": activity_count,
                "composite_score": composite,
            })

        leaderboard.sort(key=lambda x: x["composite_score"], reverse=True)

        for i, entry in enumerate(leaderboard):
            entry["rank"] = i + 1

        return leaderboard

    def _to_response(self, space: Space, user_role: str | None = None) -> SpaceResponse:
        """Convert Space model to SpaceResponse with optional role."""
        return SpaceResponse(
            id=space.id,
            user_id=space.user_id,
            name=space.name,
            description=space.description,
            color=space.color,
            learning_preferences=space.learning_preferences,
            memory_sharing_enabled=space.memory_sharing_enabled,
            tool_mode=space.tool_mode,
            enabled_tools=space.enabled_tools,
            is_collaborative=space.is_collaborative,
            user_role=user_role,
            created_at=space.created_at,
            updated_at=space.updated_at,
        )
