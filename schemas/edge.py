"""Edge Schema 定义"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from db.models import EdgeType


class EdgeBase(BaseModel):
    """边基础字段"""

    from_node_id: UUID
    to_node_id: UUID
    type: EdgeType


class EdgeCreate(EdgeBase):
    """边创建请求"""

    pass


class EdgeResponse(EdgeBase):
    """边响应（API 返回）"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    space_id: UUID
    created_at: datetime
