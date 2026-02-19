"""Activity schemas"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class ActivityTimelineItem(BaseModel):
    """学习活动时间线条目"""

    id: UUID
    title: str
    summary: str
    activity_type: str
    subject_name: str | None = None
    related_node_labels: list[str] | None = None
    message_count: int
    study_depth: str | None = None
    source: str
    activity_date: date
    activity_time: datetime
    conversation_id: UUID | None = None
    space_id: UUID | None = None
    next_review_date: date | None = None

    model_config = {"from_attributes": True}


class ActivityTimelineResponse(BaseModel):
    """学习活动时间线响应"""

    items: list[ActivityTimelineItem]
    total: int
    page: int
    limit: int
