"""Attachment Schemas - Pydantic models for request/response"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AttachmentResponse(BaseModel):
    """Response model for attachment"""

    id: UUID
    attachment_type: str
    file_url: str
    thumbnail_url: Optional[str] = None
    original_filename: str
    file_size: int
    mime_type: str
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AttachmentUploadResponse(BaseModel):
    """Response model for attachment upload"""

    success: bool = True
    attachment: AttachmentResponse
    message: str = "附件上传成功"
