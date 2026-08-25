"""文件夹模块业务逻辑"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
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

        # Check depth
        parent_depth = await self._get_folder_depth(request.parent_id)
        if parent_depth + 1 > MAX_FOLDER_DEPTH:
            raise FolderDepthExceededError(
                f"文件夹嵌套不能超过 {MAX_FOLDER_DEPTH} 层"
            )

        # If parent_id is provided, verify it exists in the same space and same content_type
        if request.parent_id:
            result = await self.db.execute(
                select(Folder).where(
                    Folder.id == request.parent_id,
                    Folder.space_id == space_id,
                    Folder.content_type == request.content_type,
                )
            )
            parent = result.scalar_one_or_none()
            if not parent:
                raise FolderNotFoundError("父文件夹不存在或类型不匹配")

        folder = Folder(
            space_id=space_id,
            parent_id=request.parent_id,
            content_type=request.content_type,
            name=request.name,
        )
        self.db.add(folder)
        await self.db.commit()
        await self.db.refresh(folder)

        return FolderResponse(
            id=folder.id,
            space_id=folder.space_id,
            parent_id=folder.parent_id,
            content_type=folder.content_type,
            name=folder.name,
            sort_order=folder.sort_order,
            created_at=folder.created_at,
            updated_at=folder.updated_at,
            children_count=0,
            items_count=0,
        )

    async def list_folders(
        self, user_id: UUID, space_id: UUID, content_type: FolderContentType
    ) -> list[FolderResponse]:
        await self._verify_space_access(user_id, space_id)

        # Count children per folder
        children_count_subq = (
            select(
                Folder.parent_id.label("pid"),
                func.count(Folder.id).label("cnt"),
            )
            .where(Folder.space_id == space_id, Folder.content_type == content_type)
            .group_by(Folder.parent_id)
            .subquery()
        )

        # Count items per folder
        if content_type == FolderContentType.NOTES:
            items_count_subq = (
                select(
                    Note.folder_id.label("fid"),
                    func.count(Note.id).label("cnt"),
                )
                .where(Note.space_id == space_id, Note.folder_id.isnot(None))
                .group_by(Note.folder_id)
                .subquery()
            )
        else:
            items_count_subq = (
                select(
                    Quiz.folder_id.label("fid"),
                    func.count(Quiz.id).label("cnt"),
                )
                .where(Quiz.space_id == space_id, Quiz.folder_id.isnot(None))
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

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            FolderResponse(
                id=folder.id,
                space_id=folder.space_id,
                parent_id=folder.parent_id,
                content_type=folder.content_type,
                name=folder.name,
                sort_order=folder.sort_order,
                created_at=folder.created_at,
                updated_at=folder.updated_at,
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

        result = await self.db.execute(
            select(Folder).where(Folder.id == folder_id, Folder.space_id == space_id)
        )
        folder = result.scalar_one_or_none()
        if not folder:
            raise FolderNotFoundError(f"文件夹 {folder_id} 不存在")

        if request.name is not None:
            folder.name = request.name

        await self.db.commit()
        await self.db.refresh(folder)

        return FolderResponse(
            id=folder.id,
            space_id=folder.space_id,
            parent_id=folder.parent_id,
            content_type=folder.content_type,
            name=folder.name,
            sort_order=folder.sort_order,
            created_at=folder.created_at,
            updated_at=folder.updated_at,
        )

    async def delete_folder(
        self, user_id: UUID, space_id: UUID, folder_id: UUID
    ) -> None:
        await self._verify_space_access(user_id, space_id)

        result = await self.db.execute(
            select(Folder).where(Folder.id == folder_id, Folder.space_id == space_id)
        )
        folder = result.scalar_one_or_none()
        if not folder:
            raise FolderNotFoundError(f"文件夹 {folder_id} 不存在")

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

        result = await self.db.execute(
            select(Folder).where(Folder.id == folder_id, Folder.space_id == space_id)
        )
        folder = result.scalar_one_or_none()
        if not folder:
            raise FolderNotFoundError(f"文件夹 {folder_id} 不存在")

        # Check no cycle
        await self._check_no_cycle(folder_id, target_parent_id)

        # Verify target parent exists and same content_type
        if target_parent_id is not None:
            parent_result = await self.db.execute(
                select(Folder).where(
                    Folder.id == target_parent_id,
                    Folder.space_id == space_id,
                    Folder.content_type == folder.content_type,
                )
            )
            if not parent_result.scalar_one_or_none():
                raise FolderNotFoundError("目标父文件夹不存在或类型不匹配")

        # Check depth: new depth = target_parent_depth + 1, and subtree must not exceed max
        target_parent_depth = await self._get_folder_depth(target_parent_id)
        if target_parent_depth + 1 > MAX_FOLDER_DEPTH:
            raise FolderDepthExceededError(
                f"移动后文件夹嵌套不能超过 {MAX_FOLDER_DEPTH} 层"
            )

        folder.parent_id = target_parent_id
        await self.db.commit()
        await self.db.refresh(folder)

        return FolderResponse(
            id=folder.id,
            space_id=folder.space_id,
            parent_id=folder.parent_id,
            content_type=folder.content_type,
            name=folder.name,
            sort_order=folder.sort_order,
            created_at=folder.created_at,
            updated_at=folder.updated_at,
        )

    async def move_notes(
        self, user_id: UUID, space_id: UUID, request: MoveItemsRequest
    ) -> int:
        await self._verify_space_access(user_id, space_id)

        # Verify target folder
        if request.target_folder_id is not None:
            result = await self.db.execute(
                select(Folder).where(
                    Folder.id == request.target_folder_id,
                    Folder.space_id == space_id,
                    Folder.content_type == FolderContentType.NOTES,
                )
            )
            if not result.scalar_one_or_none():
                raise FolderNotFoundError("目标文件夹不存在或类型不匹配")

        # Batch update
        from sqlalchemy import update

        stmt = (
            update(Note)
            .where(Note.id.in_(request.item_ids), Note.space_id == space_id)
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
            result = await self.db.execute(
                select(Folder).where(
                    Folder.id == request.target_folder_id,
                    Folder.space_id == space_id,
                    Folder.content_type == FolderContentType.QUIZZES,
                )
            )
            if not result.scalar_one_or_none():
                raise FolderNotFoundError("目标文件夹不存在或类型不匹配")

        from sqlalchemy import update

        stmt = (
            update(Quiz)
            .where(Quiz.id.in_(request.item_ids), Quiz.space_id == space_id)
            .values(folder_id=request.target_folder_id)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount
