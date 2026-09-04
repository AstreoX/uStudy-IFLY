"""笔记模块业务逻辑"""

import logging
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    Folder,
    FolderContentType,
    Node,
    Note,
    NoteAttachment,
    NoteAttachmentType,
    Space,
    User as UserModel,
)
from notes.exceptions import NoteAccessDeniedError, NoteNotFoundError
from notes.schemas import (
    AddLinkRequest,
    NoteAttachmentResponse,
    NoteCreate,
    NoteListItem,
    NoteResponse,
    NoteUpdate,
)
from upload.storage import get_storage

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


class NoteService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage = get_storage()

    async def _verify_space_access(self, user_id: UUID, space_id: UUID) -> Space:
        from spaces.authorization import (
            SpaceAccessDeniedError,
            SpaceNotFoundError,
            verify_space_access as _verify,
        )

        try:
            return await _verify(self.db, space_id, user_id)
        except SpaceNotFoundError:
            raise NoteNotFoundError(f"学习空间 {space_id} 不存在")
        except SpaceAccessDeniedError:
            raise NoteAccessDeniedError(f"无权访问学习空间 {space_id}")

    async def _get_note_with_access_check(
        self,
        user_id: UUID,
        space_id: UUID,
        note_id: UUID,
        *,
        for_write: bool = False,
    ) -> Note:
        await self._verify_space_access(user_id, space_id)

        result = await self.db.execute(
            select(Note)
            .options(selectinload(Note.attachments))
            .where(Note.id == note_id, Note.space_id == space_id)
        )
        note = result.scalar_one_or_none()

        if not note:
            raise NoteNotFoundError(f"笔记 {note_id} 不存在")

        if note.visibility == "private" and note.creator_user_id != user_id:
            if for_write:
                raise NoteNotFoundError(f"笔记 {note_id} 不存在")
            from teacher.dependencies import has_course_teacher_access

            if not await has_course_teacher_access(self.db, space_id, user_id):
                raise NoteNotFoundError(f"笔记 {note_id} 不存在")

        return note

    async def _verify_folder_for_note_write(
        self, user_id: UUID, space_id: UUID, folder_id: UUID
    ) -> None:
        folder = await self.db.scalar(
            select(Folder).where(
                Folder.id == folder_id,
                Folder.space_id == space_id,
                Folder.content_type == FolderContentType.NOTES,
                or_(
                    Folder.visibility == "shared",
                    Folder.creator_user_id == user_id,
                ),
            )
        )
        if folder is None:
            raise NoteNotFoundError(f"文件夹 {folder_id} 不存在")

    # ============ 笔记 CRUD ============

    async def create_note(
        self, user_id: UUID, space_id: UUID, request: NoteCreate
    ) -> NoteResponse:
        await self._verify_space_access(user_id, space_id)
        if request.folder_id is not None:
            await self._verify_folder_for_note_write(
                user_id, space_id, request.folder_id
            )

        note = Note(
            space_id=space_id,
            node_id=request.node_id,
            folder_id=request.folder_id,
            title=request.title,
            content=request.content,
            sort_order=request.sort_order,
            creator_user_id=user_id,
        )
        self.db.add(note)
        await self.db.commit()
        await self.db.refresh(note, attribute_names=["attachments"])

        return NoteResponse.model_validate(note)

    async def list_notes(
        self,
        user_id: UUID,
        space_id: UUID,
        node_id: Optional[UUID] = None,
        free_only: bool = False,
        folder_id: Optional[UUID] = None,
    ) -> list[NoteListItem]:
        await self._verify_space_access(user_id, space_id)

        from teacher.dependencies import has_course_teacher_access

        can_read_all_private = await has_course_teacher_access(
            self.db, space_id, user_id
        )

        stmt = (
            select(
                Note,
                func.count(NoteAttachment.id).label("attachment_count"),
                Node.label.label("node_label"),
                UserModel.nickname.label("creator_nickname"),
            )
            .outerjoin(Node, Node.id == Note.node_id)
            .outerjoin(NoteAttachment, NoteAttachment.note_id == Note.id)
            .outerjoin(UserModel, UserModel.id == Note.creator_user_id)
            .where(Note.space_id == space_id)
            .group_by(Note.id, Node.label, UserModel.nickname)
            .order_by(Note.sort_order.asc(), Note.created_at.desc())
        )
        if not can_read_all_private:
            stmt = stmt.where(
                or_(
                    Note.visibility == "shared",
                    Note.creator_user_id == user_id,
                )
            )

        if node_id is not None:
            stmt = stmt.where(Note.node_id == node_id)
        elif free_only:
            stmt = stmt.where(Note.node_id.is_(None))

        # folder_id filtering: explicit value filters by folder, "root" means folder_id IS NULL
        if folder_id is not None:
            stmt = stmt.where(Note.folder_id == folder_id)

        result = await self.db.execute(stmt)
        rows = result.all()

        return [
            NoteListItem(
                id=note.id,
                space_id=note.space_id,
                node_id=note.node_id,
                node_label=node_label,
                folder_id=note.folder_id,
                title=note.title,
                content=note.content,
                note_type=note.note_type,
                metadata_=note.metadata_,
                sort_order=note.sort_order,
                created_at=note.created_at,
                updated_at=note.updated_at,
                attachment_count=count,
                creator_user_id=note.creator_user_id,
                creator_nickname=creator_nickname,
                visibility=note.visibility,
            )
            for note, count, node_label, creator_nickname in rows
        ]

    async def get_note(
        self, user_id: UUID, space_id: UUID, note_id: UUID
    ) -> NoteResponse:
        note = await self._get_note_with_access_check(user_id, space_id, note_id)
        resp = NoteResponse.model_validate(note)
        if note.node_id:
            node_result = await self.db.execute(
                select(Node.label).where(Node.id == note.node_id)
            )
            resp.node_label = node_result.scalar_one_or_none()
        if note.creator_user_id:
            creator_result = await self.db.execute(
                select(UserModel.nickname).where(UserModel.id == note.creator_user_id)
            )
            resp.creator_nickname = creator_result.scalar_one_or_none()
        return resp

    async def update_note(
        self, user_id: UUID, space_id: UUID, note_id: UUID, request: NoteUpdate
    ) -> NoteResponse:
        note = await self._get_note_with_access_check(
            user_id, space_id, note_id, for_write=True
        )

        # Check collaborative permissions
        space = await self._verify_space_access(user_id, space_id)
        if space.is_collaborative and note.creator_user_id and note.creator_user_id != user_id:
            if space.user_id != user_id:  # Not the owner
                raise NoteAccessDeniedError("只有管理员可以编辑他人的笔记")

        provided = request.model_fields_set
        if "title" in provided:
            note.title = request.title
        if "content" in provided:
            note.content = request.content
        if "node_id" in provided:
            note.node_id = request.node_id
        if "sort_order" in provided:
            note.sort_order = request.sort_order

        await self.db.commit()

        # Re-fetch with eagerly loaded attachments to avoid MissingGreenlet
        result = await self.db.execute(
            select(Note)
            .options(selectinload(Note.attachments))
            .where(Note.id == note_id)
        )
        note = result.scalar_one()

        return NoteResponse.model_validate(note)

    async def delete_note(
        self, user_id: UUID, space_id: UUID, note_id: UUID
    ) -> None:
        note = await self._get_note_with_access_check(
            user_id, space_id, note_id, for_write=True
        )

        # Check collaborative permissions
        space = await self._verify_space_access(user_id, space_id)
        if space.is_collaborative and note.creator_user_id and note.creator_user_id != user_id:
            if space.user_id != user_id:  # Not the owner
                raise NoteAccessDeniedError("只有管理员可以删除他人的笔记")

        # Delete attachment files from storage
        for att in note.attachments:
            if att.file_url:
                try:
                    await self.storage.delete(att.file_url)
                except Exception as e:
                    logger.warning("Failed to delete file %s: %s", att.file_url, e)

        await self.db.delete(note)
        await self.db.commit()

        logger.info("Deleted note %s from space %s", note_id, space_id)

    # ============ 附件操作 ============

    async def add_attachment(
        self,
        user_id: UUID,
        space_id: UUID,
        note_id: UUID,
        file_data: bytes,
        original_filename: str,
        mime_type: str,
    ) -> NoteAttachmentResponse:
        note = await self._get_note_with_access_check(
            user_id, space_id, note_id, for_write=True
        )

        is_image = mime_type.startswith("image/")
        att_type = NoteAttachmentType.IMAGE if is_image else NoteAttachmentType.FILE

        unique_id = uuid4()
        ext = original_filename.rsplit(".", 1)[-1] if "." in original_filename else "bin"
        filename = f"{unique_id}.{ext}"
        subdir = "notes/images" if is_image else "notes/files"

        file_url = await self.storage.save(file_data, filename, subdir=subdir)

        attachment = NoteAttachment(
            note_id=note.id,
            attachment_type=att_type,
            file_url=file_url,
            original_filename=original_filename,
            file_size=len(file_data),
            mime_type=mime_type,
        )
        self.db.add(attachment)
        await self.db.commit()
        await self.db.refresh(attachment)

        logger.info("Added attachment %s to note %s", attachment.id, note_id)
        return NoteAttachmentResponse.model_validate(attachment)

    async def add_link(
        self,
        user_id: UUID,
        space_id: UUID,
        note_id: UUID,
        request: AddLinkRequest,
    ) -> NoteAttachmentResponse:
        await self._get_note_with_access_check(
            user_id, space_id, note_id, for_write=True
        )

        attachment = NoteAttachment(
            note_id=note_id,
            attachment_type=NoteAttachmentType.LINK,
            link_url=request.link_url,
            link_title=request.link_title,
        )
        self.db.add(attachment)
        await self.db.commit()
        await self.db.refresh(attachment)

        logger.info("Added link to note %s: %s", note_id, request.link_url)
        return NoteAttachmentResponse.model_validate(attachment)

    async def delete_attachment(
        self,
        user_id: UUID,
        space_id: UUID,
        note_id: UUID,
        attachment_id: UUID,
    ) -> None:
        await self._get_note_with_access_check(
            user_id, space_id, note_id, for_write=True
        )

        result = await self.db.execute(
            select(NoteAttachment).where(
                NoteAttachment.id == attachment_id,
                NoteAttachment.note_id == note_id,
            )
        )
        attachment = result.scalar_one_or_none()

        if not attachment:
            raise NoteNotFoundError(f"附件 {attachment_id} 不存在")

        # Delete file from storage if it exists
        if attachment.file_url:
            try:
                await self.storage.delete(attachment.file_url)
            except Exception as e:
                logger.warning("Failed to delete file %s: %s", attachment.file_url, e)

        await self.db.delete(attachment)
        await self.db.commit()

        logger.info("Deleted attachment %s from note %s", attachment_id, note_id)
