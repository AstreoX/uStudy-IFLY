"""Attachment Router - API endpoints for attachment management"""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from attachments.schemas import AttachmentUploadResponse
from attachments.service import (
    AttachmentAccessDeniedError,
    AttachmentAlreadyAttachedError,
    AttachmentNotFoundError,
    AttachmentService,
)
from attachments.validators import FileValidationError, MAX_FILE_SIZE
from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/attachments", tags=["attachments"])


async def read_file_with_limit(file: UploadFile, max_size: int = MAX_FILE_SIZE) -> bytes:
    """
    Read uploaded file in chunks with size limit to prevent memory exhaustion.

    Args:
        file: Uploaded file
        max_size: Maximum file size in bytes

    Returns:
        File content as bytes

    Raises:
        FileValidationError: If file exceeds size limit
    """
    chunks = []
    total = 0

    while True:
        chunk = await file.read(8192)  # Read 8KB at a time
        if not chunk:
            break

        total += len(chunk)
        if total > max_size:
            raise FileValidationError(
                f"文件大小超过限制 (最大 {max_size / 1024 / 1024:.0f}MB)"
            )

        chunks.append(chunk)

    return b"".join(chunks)


@router.post("/upload", response_model=AttachmentUploadResponse)
async def upload_attachment(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AttachmentUploadResponse:
    """
    Upload an attachment (image or file).

    Creates an orphan attachment (not yet associated with a message).
    The attachment will be associated with a message when sending.

    Supported image formats: JPEG, PNG, WebP, GIF
    Supported file formats: PDF, Word, Excel, PowerPoint, TXT
    Max file size: 10MB
    """
    try:
        # Read file data with size limit (stream read to prevent memory exhaustion)
        file_data = await read_file_with_limit(file)

        # Get original filename
        original_filename = file.filename or "unnamed"

        # Upload attachment
        service = AttachmentService(db)
        attachment = await service.upload_attachment(
            user_id=current_user.id,
            file_data=file_data,
            original_filename=original_filename,
            claimed_mime=file.content_type,
        )

        return AttachmentUploadResponse(
            success=True,
            attachment=attachment,
            message="附件上传成功",
        )

    except FileValidationError as e:
        logger.warning(f"File validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Attachment upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="附件上传失败，请稍后重试",
        )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_orphan_attachment(
    attachment_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Delete an orphan attachment (not yet attached to a message).

    Only orphan attachments can be deleted via this endpoint.
    Attachments already associated with messages will be deleted
    when the message is deleted (cascade).
    """
    try:
        service = AttachmentService(db)
        await service.delete_orphan_attachment(
            user_id=current_user.id,
            attachment_id=attachment_id,
        )

    except AttachmentNotFoundError as e:
        logger.warning(f"Attachment not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except AttachmentAccessDeniedError as e:
        logger.warning(f"Attachment access denied: {e}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except AttachmentAlreadyAttachedError as e:
        logger.warning(f"Attachment already attached: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Attachment deletion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="附件删除失败，请稍后重试",
        )
