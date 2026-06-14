"""Attachment Service - Business logic for attachment management"""

import logging
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from attachments.schemas import AttachmentResponse
from attachments.validators import (
    FileValidationError,
    compress_image,
    detect_file_type,
    generate_thumbnail,
    get_file_extension,
    sanitize_filename,
    validate_file_size,
    validate_file_type,
)
from db.models import AttachmentType, MessageAttachment
from upload.storage import get_storage

logger = logging.getLogger(__name__)


class AttachmentNotFoundError(Exception):
    """Raised when attachment is not found"""

    pass


class AttachmentAccessDeniedError(Exception):
    """Raised when user doesn't have access to attachment"""

    pass


class AttachmentAlreadyAttachedError(Exception):
    """Raised when trying to attach an already attached attachment"""

    pass


class AttachmentService:
    """Service for attachment operations"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.storage = get_storage()

    async def upload_attachment(
        self,
        user_id: UUID,
        file_data: bytes,
        original_filename: str,
        claimed_mime: str | None = None,
    ) -> AttachmentResponse:
        """
        Upload an attachment (image or file).

        Creates a MessageAttachment record with message_id=None (orphan).
        The attachment will be associated with a message later.

        Args:
            user_id: User ID uploading the attachment
            file_data: File binary data
            original_filename: Original filename from user

        Returns:
            AttachmentResponse with attachment details

        Raises:
            FileValidationError: If file validation fails
        """
        # 1. Sanitize original filename
        original_filename = sanitize_filename(original_filename)

        # 2. Validate file size (although router already checked via stream read)
        validate_file_size(file_data)

        # 3. Detect file type using magic bytes
        detected_mime_type = detect_file_type(
            file_data,
            filename=original_filename,
            claimed_mime=claimed_mime,
        )
        logger.info(
            "Detected MIME type: %s for file: %s", detected_mime_type, original_filename
        )

        # 4. Determine if it's an image or file
        is_image = detected_mime_type.startswith("image/")
        attachment_type = AttachmentType.IMAGE if is_image else AttachmentType.FILE

        # 5. Validate file type
        validate_file_type(detected_mime_type, is_image)

        # 6. Process file
        width: Optional[int] = None
        height: Optional[int] = None
        thumbnail_url: Optional[str] = None
        file_size: int
        file_url: str

        if is_image:
            # Compress image to WebP
            compressed_data, width, height = compress_image(file_data)

            # Generate thumbnail
            thumbnail_data = generate_thumbnail(file_data)

            # Save main image
            unique_id = uuid4()
            image_filename = f"{unique_id}.webp"
            file_url = await self.storage.save(
                compressed_data, image_filename, subdir="attachments/images"
            )
            file_size = len(compressed_data)

            # Save thumbnail
            thumbnail_filename = f"{unique_id}_thumb.webp"
            thumbnail_url = await self.storage.save(
                thumbnail_data, thumbnail_filename, subdir="attachments/thumbnails"
            )

            # Update mime type to WebP (since we converted)
            detected_mime_type = "image/webp"

        else:
            # Save file as-is
            unique_id = uuid4()
            original_suffix = Path(original_filename).suffix.lower().lstrip(".")
            extension = original_suffix or get_file_extension(detected_mime_type)
            file_filename = f"{unique_id}.{extension}"
            file_url = await self.storage.save(
                file_data, file_filename, subdir="attachments/files"
            )
            file_size = len(file_data)

        # 7. Create MessageAttachment record (orphan, message_id=None)
        attachment = MessageAttachment(
            message_id=None,  # Orphan attachment
            user_id=user_id,
            attachment_type=attachment_type,
            file_url=file_url,
            original_filename=original_filename,
            file_size=file_size,
            mime_type=detected_mime_type,
            width=width,
            height=height,
            thumbnail_url=thumbnail_url,
        )

        self.db.add(attachment)
        await self.db.commit()
        await self.db.refresh(attachment)

        logger.info(
            "Uploaded attachment %s (type=%s, size=%d)",
            attachment.id,
            attachment_type.value,
            file_size,
        )

        return AttachmentResponse.model_validate(attachment)

    async def attach_to_message(
        self,
        user_id: UUID,
        message_id: UUID,
        attachment_ids: list[UUID],
        commit: bool = True,
    ) -> None:
        """
        Associate orphan attachments with a message.

        Args:
            user_id: User ID (for ownership validation)
            message_id: Message ID to attach to
            attachment_ids: List of attachment IDs to attach
            commit: Whether to commit the transaction (default True)

        Raises:
            AttachmentNotFoundError: If any attachment not found
            AttachmentAccessDeniedError: If user doesn't own an attachment
            AttachmentAlreadyAttachedError: If attachment already attached
        """
        if not attachment_ids:
            return

        # Fetch all attachments
        result = await self.db.execute(
            select(MessageAttachment).where(MessageAttachment.id.in_(attachment_ids))
        )
        attachments = result.scalars().all()

        # Validate all attachments exist
        if len(attachments) != len(attachment_ids):
            found_ids = {att.id for att in attachments}
            missing_ids = set(attachment_ids) - found_ids
            raise AttachmentNotFoundError(f"附件未找到: {missing_ids}")

        # Validate ownership and orphan status
        for attachment in attachments:
            if attachment.user_id != user_id:
                raise AttachmentAccessDeniedError(
                    f"无权访问附件 {attachment.id}"
                )

            if attachment.message_id is not None:
                raise AttachmentAlreadyAttachedError(
                    f"附件 {attachment.id} 已关联到消息 {attachment.message_id}"
                )

            # Associate with message
            attachment.message_id = message_id

        if commit:
            await self.db.commit()

        logger.info(
            "Attached %d attachments to message %s", len(attachments), message_id
        )

    async def delete_orphan_attachment(
        self,
        user_id: UUID,
        attachment_id: UUID,
    ) -> None:
        """
        Delete an orphan attachment (not yet attached to a message).

        Args:
            user_id: User ID (for ownership validation)
            attachment_id: Attachment ID to delete

        Raises:
            AttachmentNotFoundError: If attachment not found
            AttachmentAccessDeniedError: If user doesn't own the attachment
            AttachmentAlreadyAttachedError: If attachment is already attached
        """
        # Fetch attachment
        result = await self.db.execute(
            select(MessageAttachment).where(MessageAttachment.id == attachment_id)
        )
        attachment = result.scalar_one_or_none()

        if not attachment:
            raise AttachmentNotFoundError(f"附件 {attachment_id} 不存在")

        if attachment.user_id != user_id:
            raise AttachmentAccessDeniedError(f"无权访问附件 {attachment_id}")

        if attachment.message_id is not None:
            raise AttachmentAlreadyAttachedError(
                f"附件已关联到消息，无法删除"
            )

        # Delete files from storage
        await self.storage.delete(attachment.file_url)
        if attachment.thumbnail_url:
            await self.storage.delete(attachment.thumbnail_url)

        # Delete database record
        await self.db.delete(attachment)
        await self.db.commit()

        logger.info("Deleted orphan attachment %s", attachment_id)

    async def get_attachment(
        self,
        user_id: UUID,
        attachment_id: UUID,
    ) -> AttachmentResponse:
        """
        Get attachment details.

        Args:
            user_id: User ID (for ownership validation)
            attachment_id: Attachment ID

        Returns:
            AttachmentResponse

        Raises:
            AttachmentNotFoundError: If attachment not found
            AttachmentAccessDeniedError: If user doesn't own the attachment
        """
        result = await self.db.execute(
            select(MessageAttachment).where(MessageAttachment.id == attachment_id)
        )
        attachment = result.scalar_one_or_none()

        if not attachment:
            raise AttachmentNotFoundError(f"附件 {attachment_id} 不存在")

        if attachment.user_id != user_id:
            raise AttachmentAccessDeniedError(f"无权访问附件 {attachment_id}")

        return AttachmentResponse.model_validate(attachment)
