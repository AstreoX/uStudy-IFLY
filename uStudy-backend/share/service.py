"""分享功能业务逻辑"""

import logging
import secrets
from uuid import UUID, uuid4

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    Edge,
    EdgeType,
    Node,
    Note,
    NoteAttachment,
    NoteAttachmentType,
    Space,
    SpaceShareCode,
)
from share.schemas import ShareCodeResponse
from spaces.schemas import SpaceResponse

logger = logging.getLogger(__name__)

# Charset excluding ambiguous characters: 0/O, 1/I/L
SHARE_CODE_CHARSET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


class ShareCodeError(Exception):
    pass


class ShareService:

    @staticmethod
    def _generate_code(length: int = 8) -> str:
        return "".join(secrets.choice(SHARE_CODE_CHARSET) for _ in range(length))

    @staticmethod
    def _format_display_code(code: str) -> str:
        return f"{code[:4]}-{code[4:]}"

    @staticmethod
    async def generate_share_code(
        db: AsyncSession, user_id: UUID, space_id: UUID
    ) -> ShareCodeResponse:
        # Verify space exists and user owns it
        space = await db.get(Space, space_id)
        if not space:
            raise ShareCodeError("学习空间不存在")
        if space.user_id != user_id:
            raise ShareCodeError("无权分享此学习空间")

        # Check if code already exists for this space
        existing = await db.execute(
            select(SpaceShareCode).where(SpaceShareCode.space_id == space_id)
        )
        existing_record = existing.scalar_one_or_none()

        if existing_record:
            # Return existing code
            return ShareCodeResponse(
                code=existing_record.code,
                display_code=ShareService._format_display_code(existing_record.code),
                space_name=space.name,
                created_at=existing_record.created_at,
            )

        # Generate unique code with retry
        for _ in range(10):
            code = ShareService._generate_code()
            conflict = await db.execute(
                select(SpaceShareCode).where(SpaceShareCode.code == code)
            )
            if not conflict.scalar_one_or_none():
                break
        else:
            raise ShareCodeError("生成分享码失败，请重试")

        share_record = SpaceShareCode(
            id=uuid4(),
            code=code,
            space_id=space_id,
            creator_user_id=user_id,
        )
        db.add(share_record)
        await db.commit()
        await db.refresh(share_record)

        return ShareCodeResponse(
            code=share_record.code,
            display_code=ShareService._format_display_code(share_record.code),
            space_name=space.name,
            created_at=share_record.created_at,
        )

    @staticmethod
    async def import_space(
        db: AsyncSession, user_id: UUID, share_code: str
    ) -> SpaceResponse:
        # Normalize: uppercase, strip hyphens/spaces
        normalized = share_code.upper().replace("-", "").replace(" ", "").strip()
        if not normalized or len(normalized) != 8:
            raise ShareCodeError("分享码格式无效，请输入8位分享码")

        # Look up code
        result = await db.execute(
            select(SpaceShareCode).where(SpaceShareCode.code == normalized)
        )
        share_record = result.scalar_one_or_none()
        if not share_record:
            raise ShareCodeError("分享码不存在或已失效")

        # Load source space
        source_space = await db.get(Space, share_record.space_id)
        if not source_space:
            raise ShareCodeError("源学习空间已被删除")

        # --- Deep copy in a single transaction ---

        # 1. Create new space (copy name, description, color only)
        new_space = Space(
            user_id=user_id,
            name=source_space.name,
            description=source_space.description,
            color=source_space.color,
        )
        db.add(new_space)
        await db.flush()  # get new_space.id

        # 2. Copy nodes (label only, mastery=NULL)
        source_nodes = await db.execute(
            select(Node).where(Node.space_id == source_space.id)
        )
        old_to_new_node: dict[UUID, UUID] = {}
        label_to_new_node: dict[str, UUID] = {}
        for node in source_nodes.scalars().all():
            new_node = Node(
                space_id=new_space.id,
                label=node.label,
                mastery=None,
            )
            db.add(new_node)
            await db.flush()
            old_to_new_node[node.id] = new_node.id
            label_to_new_node[node.label] = new_node.id

        # 3. Copy edges (KNOWLEDGE_TREE and ADVANCED only, skip LEARNING_PATH)
        source_edges = await db.execute(
            select(Edge).where(
                Edge.space_id == source_space.id,
                Edge.type.in_([EdgeType.KNOWLEDGE_TREE, EdgeType.ADVANCED]),
            )
        )
        for edge in source_edges.scalars().all():
            new_from = old_to_new_node.get(edge.from_node_id)
            new_to = old_to_new_node.get(edge.to_node_id)
            if new_from and new_to:
                db.add(Edge(
                    space_id=new_space.id,
                    from_node_id=new_from,
                    to_node_id=new_to,
                    type=edge.type,
                ))

        # 4. Copy notes (title, content, note_type, metadata_, sort_order)
        source_notes = await db.execute(
            select(Note)
            .where(Note.space_id == source_space.id)
            .options(selectinload(Note.attachments))
        )
        for note in source_notes.scalars().all():
            # Remap node_id via label match
            new_node_id = None
            if note.node_id and note.node_id in old_to_new_node:
                new_node_id = old_to_new_node[note.node_id]

            new_note = Note(
                space_id=new_space.id,
                node_id=new_node_id,
                title=note.title,
                content=note.content,
                note_type=note.note_type,
                metadata_=note.metadata_,
                sort_order=note.sort_order,
            )
            db.add(new_note)
            await db.flush()

            # 5. Copy LINK attachments only
            for att in note.attachments:
                if att.attachment_type == NoteAttachmentType.LINK:
                    db.add(NoteAttachment(
                        note_id=new_note.id,
                        attachment_type=NoteAttachmentType.LINK,
                        link_url=att.link_url,
                        link_title=att.link_title,
                        sort_order=att.sort_order,
                    ))

        await db.commit()
        await db.refresh(new_space)

        return SpaceResponse.model_validate(new_space)
