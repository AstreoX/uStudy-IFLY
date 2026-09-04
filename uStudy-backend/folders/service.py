"""文件夹模块业务逻辑"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Folder, FolderContentType, Note, Quiz
from folders.schemas import (
    FolderCreate,
    FolderResponse,
    FolderUpdate,
    MoveItemsRequest,
)

logger = logging.getLogger(__name__)

MAX_FOLDER_DEPTH = 3


class FolderNotFoundError(Exception):
    pass


class FolderAccessDeniedError(Exception):
    pass


class FolderDepthExceededError(Exception):
    pass


class FolderCyclicError(Exception):
    pass


class FolderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _verify_space_access(self, user_id: UUID, space_id: UUID) -> None:
        from spaces.authorization import (
            SpaceAccessDeniedError,
            SpaceNotFoundError,
            verify_space_access,
        )

        try:
            await verify_space_access(self.db, space_id, user_id)
        except SpaceNotFoundError:
            raise FolderNotFoundError(f"学习空间 {space_id} 不存在")
        except SpaceAccessDeniedError:
            raise FolderAccessDeniedError(f"无权访问学习空间 {space_id}")

    @staticmethod
    def _private_or_owned(model, user_id: UUID):
        return or_(model.visibility == "shared", model.creator_user_id == user_id)

    async def _can_read_all_note_folders(
        self, user_id: UUID, space_id: UUID
    ) -> bool:
        from teacher.dependencies import has_course_teacher_access

        return await has_course_teacher_access(self.db, space_id, user_id)

    async def _get_folder_for_write(
        self,
        user_id: UUID,
        space_id: UUID,
        folder_id: UUID,
        *,
        content_type: FolderContentType | None = None,
    ) -> Folder:
        conditions = [
            Folder.id == folder_id,
            Folder.space_id == space_id,
            self._private_or_owned(Folder, user_id),
        ]
        if content_type is not None:
            conditions.append(Folder.content_type == content_type)
        folder = await self.db.scalar(select(Folder).where(*conditions))
        if folder is None:
            raise FolderNotFoundError(f"文件夹 {folder_id} 不存在")
        return folder

    async def _ensure_subtree_writable(
        self, user_id: UUID, space_id: UUID, folder_id: UUID
    ) -> None:
        """Prevent shared-folder operations from mutating nested private content."""
        all_ids = {folder_id}
        frontier = {folder_id}
        while frontier:
            rows = (
                await self.db.execute(
                    select(
                        Folder.id,
                        Folder.visibility,
                        Folder.creator_user_id,
                    ).where(
                        Folder.space_id == space_id,
                        Folder.parent_id.in_(frontier),
                    )
                )
            ).all()
            for row in rows:
                if row.visibility == "private" and row.creator_user_id != user_id:
                    raise FolderNotFoundError(f"文件夹 {folder_id} 不存在")
            frontier = {row.id for row in rows} - all_ids
            all_ids.update(frontier)

        private_note = await self.db.scalar(
            select(Note.id).where(
                Note.space_id == space_id,
                Note.folder_id.in_(all_ids),
                Note.visibility == "private",
                or_(
                    Note.creator_user_id != user_id,
                    Note.creator_user_id.is_(None),
                ),
            ).limit(1)
        )
        private_quiz = await self.db.scalar(
            select(Quiz.id).where(
                Quiz.space_id == space_id,
                Quiz.folder_id.in_(all_ids),
                Quiz.visibility == "private",
                or_(
                    Quiz.creator_user_id != user_id,
                    Quiz.creator_user_id.is_(None),
                ),
            ).limit(1)
        )
        if private_note is not None or private_quiz is not None:
            raise FolderNotFoundError(f"文件夹 {folder_id} 不存在")

    @staticmethod
    def _response(
        folder: Folder, *, children_count: int = 0, items_count: int = 0
    ) -> FolderResponse:
        return FolderResponse(
            id=folder.id,
            space_id=folder.space_id,
            parent_id=folder.parent_id,
            content_type=folder.content_type,
            name=folder.name,
            creator_user_id=folder.creator_user_id,
            visibility=folder.visibility,
            sort_order=folder.sort_order,
            created_at=folder.created_at,
            updated_at=folder.updated_at,
            children_count=children_count,
            items_count=items_count,
        )

    async def _get_folder_depth(self, folder_id: Optional[UUID]) -> int:
        """Calculate depth of a folder (root = 1). Returns 0 if folder_id is None."""
        if folder_id is None:
            return 0
        depth = 0
        current_id = folder_id
        while current_id is not None:
            depth += 1
            result = await self.db.execute(
                select(Folder.parent_id).where(Folder.id == current_id)
            )
            row = result.scalar_one_or_none()
            current_id = row
        return depth

    async def _check_no_cycle(
        self, folder_id: UUID, target_parent_id: Optional[UUID]
    ) -> None:
        """Ensure moving folder_id under target_parent_id doesn't create a cycle."""
        if target_parent_id is None:
            return
        current_id = target_parent_id
        while current_id is not None:
            if current_id == folder_id:
                raise FolderCyclicError("移动操作会导致循环引用")
            result = await self.db.execute(
                select(Folder.parent_id).where(Folder.id == current_id)
            )
            current_id = result.scalar_one_or_none()

    async def create_folder(
        self, user_id: UUID, space_id: UUID, request: FolderCreate
    ) -> FolderResponse:
        await self._verify_space_access(user_id, space_id)

        # If parent_id is provided, verify it exists in the same space and same content_type
        if request.parent_id:
            parent = await self._get_folder_for_write(
                user_id,
                space_id,
                request.parent_id,
                content_type=request.content_type,
            )
            # API-created folders stay shared; do not create a visible child beneath
            # an imported private parent that other members cannot see.
            if parent.visibility == "private":
                raise FolderNotFoundError("父文件夹不存在或类型不匹配")

        # Check depth only after the parent has passed ACL validation.
        parent_depth = await self._get_folder_depth(request.parent_id)
        if parent_depth + 1 > MAX_FOLDER_DEPTH:
            raise FolderDepthExceededError(
                f"文件夹嵌套不能超过 {MAX_FOLDER_DEPTH} 层"
            )

        folder = Folder(
            space_id=space_id,
            parent_id=request.parent_id,
            content_type=request.content_type,
            name=request.name,
            creator_user_id=user_id,
            visibility="shared",
        )
        self.db.add(folder)
        await self.db.commit()
        await self.db.refresh(folder)

        return self._response(folder)

    async def list_folders(
        self, user_id: UUID, space_id: UUID, content_type: FolderContentType
    ) -> list[FolderResponse]:
        await self._verify_space_access(user_id, space_id)

        can_read_all_private = (
            content_type == FolderContentType.NOTES
            and await self._can_read_all_note_folders(user_id, space_id)
        )
        folder_visibility = self._private_or_owned(Folder, user_id)
        note_visibility = self._private_or_owned(Note, user_id)
        quiz_visibility = self._private_or_owned(Quiz, user_id)

        # Count children per folder
        children_count_subq = (
            select(
                Folder.parent_id.label("pid"),
                func.count(Folder.id).label("cnt"),
            )
            .where(Folder.space_id == space_id, Folder.content_type == content_type)
        )
        if not can_read_all_private:
            children_count_subq = children_count_subq.where(folder_visibility)
        children_count_subq = children_count_subq.group_by(Folder.parent_id).subquery()

        # Count items per folder
        if content_type == FolderContentType.NOTES:
            items_count_subq = (
                select(
                    Note.folder_id.label("fid"),
                    func.count(Note.id).label("cnt"),
                )
                .where(Note.space_id == space_id, Note.folder_id.isnot(None))
            )
            if not can_read_all_private:
                items_count_subq = items_count_subq.where(note_visibility)
            items_count_subq = items_count_subq.group_by(Note.folder_id).subquery()
        else:
            items_count_subq = (
                select(
                    Quiz.folder_id.label("fid"),
                    func.count(Quiz.id).label("cnt"),
                )
                .where(Quiz.space_id == space_id, Quiz.folder_id.isnot(None))
                .where(quiz_visibility)
                .group_by(Quiz.folder_id)
                .subquery()
            )

        stmt = (
            select(
                Folder,
                func.coalesce(children_count_subq.c.cnt, 0).label("children_count"),
                func.coalesce(items_count_subq.c.cnt, 0).label("items_count"),
            )
            .outerjoin(
                children_count_subq, children_count_subq.c.pid == Folder.id
            )
            .outerjoin(items_count_subq, items_count_subq.c.fid == Folder.id)
            .where(Folder.space_id == space_id, Folder.content_type == content_type)
            .order_by(Folder.sort_order.asc(), Folder.created_at.asc())
        )
        if not can_read_all_private:
            stmt = stmt.where(folder_visibility)

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            self._response(
                folder,
                children_count=children_count,
                items_count=items_count,
            )
            for folder, children_count, items_count in rows
        ]

    async def update_folder(
        self,
        user_id: UUID,
        space_id: UUID,
        folder_id: UUID,
        request: FolderUpdate,
    ) -> FolderResponse:
        await self._verify_space_access(user_id, space_id)

        folder = await self._get_folder_for_write(user_id, space_id, folder_id)
        await self._ensure_subtree_writable(user_id, space_id, folder_id)

        if request.name is not None:
            folder.name = request.name

        await self.db.commit()
        await self.db.refresh(folder)

        return self._response(folder)

    async def delete_folder(
        self, user_id: UUID, space_id: UUID, folder_id: UUID
    ) -> None:
        await self._verify_space_access(user_id, space_id)

        folder = await self._get_folder_for_write(user_id, space_id, folder_id)
        await self._ensure_subtree_writable(user_id, space_id, folder_id)

        # CASCADE will delete child folders; folder_id on notes/quizzes SET NULL
        await self.db.delete(folder)
        await self.db.commit()

        logger.info("Deleted folder %s from space %s", folder_id, space_id)

    async def move_folder(
        self,
        user_id: UUID,
        space_id: UUID,
        folder_id: UUID,
        target_parent_id: Optional[UUID],
    ) -> FolderResponse:
        await self._verify_space_access(user_id, space_id)

        folder = await self._get_folder_for_write(user_id, space_id, folder_id)
        await self._ensure_subtree_writable(user_id, space_id, folder_id)

        # Verify target parent exists and same content_type
        if target_parent_id is not None:
            await self._get_folder_for_write(
                user_id,
                space_id,
                target_parent_id,
                content_type=folder.content_type,
            )

        # Check no cycle only after the target has passed ACL validation.
        await self._check_no_cycle(folder_id, target_parent_id)

        # Check depth: new depth = target_parent_depth + 1, and subtree must not exceed max
        target_parent_depth = await self._get_folder_depth(target_parent_id)
        if target_parent_depth + 1 > MAX_FOLDER_DEPTH:
            raise FolderDepthExceededError(
                f"移动后文件夹嵌套不能超过 {MAX_FOLDER_DEPTH} 层"
            )

        folder.parent_id = target_parent_id
        await self.db.commit()
        await self.db.refresh(folder)

        return self._response(folder)

    async def move_notes(
        self, user_id: UUID, space_id: UUID, request: MoveItemsRequest
    ) -> int:
        await self._verify_space_access(user_id, space_id)

        # Verify target folder
        if request.target_folder_id is not None:
            await self._get_folder_for_write(
                user_id,
                space_id,
                request.target_folder_id,
                content_type=FolderContentType.NOTES,
            )

        requested_ids = set(request.item_ids)
        writable_ids = set(
            (
                await self.db.execute(
                    select(Note.id).where(
                        Note.id.in_(requested_ids),
                        Note.space_id == space_id,
                        self._private_or_owned(Note, user_id),
                    )
                )
            ).scalars()
        )
        if writable_ids != requested_ids:
            raise FolderNotFoundError("部分笔记不存在")

        stmt = (
            update(Note)
            .where(Note.id.in_(writable_ids), Note.space_id == space_id)
            .values(folder_id=request.target_folder_id)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def move_quizzes(
        self, user_id: UUID, space_id: UUID, request: MoveItemsRequest
    ) -> int:
        await self._verify_space_access(user_id, space_id)

        if request.target_folder_id is not None:
            await self._get_folder_for_write(
                user_id,
                space_id,
                request.target_folder_id,
                content_type=FolderContentType.QUIZZES,
            )

        requested_ids = set(request.item_ids)
        writable_ids = set(
            (
                await self.db.execute(
                    select(Quiz.id).where(
                        Quiz.id.in_(requested_ids),
                        Quiz.space_id == space_id,
                        self._private_or_owned(Quiz, user_id),
                    )
                )
            ).scalars()
        )
        if writable_ids != requested_ids:
            raise FolderNotFoundError("部分测试不存在")

        stmt = (
            update(Quiz)
            .where(Quiz.id.in_(writable_ids), Quiz.space_id == space_id)
            .values(folder_id=request.target_folder_id)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount
