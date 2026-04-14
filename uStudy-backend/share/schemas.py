"""分享功能 Pydantic Schema"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ShareCodeResponse(BaseModel):
    """分享码响应"""

    code: str = Field(..., description="原始8位分享码")
    display_code: str = Field(..., description="格式化显示码 XXXX-XXXX")
    space_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportSpaceRequest(BaseModel):
    """导入空间请求"""

    share_code: str = Field(..., min_length=4, max_length=12, description="分享码（可含连字符）")
