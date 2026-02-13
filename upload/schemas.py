"""上传模块 Schema 定义"""

from typing import Optional

from pydantic import BaseModel


class AvatarUploadResponse(BaseModel):
    """头像上传响应"""

    success: bool
    avatar_url: str
    message: Optional[str] = None


class UploadError(BaseModel):
    """上传错误响应"""

    success: bool = False
    error: str
    detail: Optional[str] = None
