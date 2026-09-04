"""Review schedule schemas"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class ReviewScheduleItem(BaseModel):
    """单条复习计划"""

    id: UUID
    node_label: str | None = None
    review_number: int
    scheduled_date: date
    status: str
    completed_at: datetime | None = None
    study_depth: str | None = None
    ease_factor: float = 2.5
    interval_days: int = 1
    quality_score: int | None = None
    review_quiz_id: UUID | None = None

    model_config = {"from_attributes": True}


class ActivityReviewsResponse(BaseModel):
    """某活动的复习计划响应"""

    activity_id: UUID
    items: list[ReviewScheduleItem]


class DueReviewItem(BaseModel):
    """到期复习项"""

    id: UUID
    activity_id: UUID
    node_label: str | None = None
    review_number: int
    scheduled_date: date
    study_depth: str | None = None
    days_overdue: int = 0

    model_config = {"from_attributes": True}


class DueReviewsResponse(BaseModel):
    """到期复习列表响应"""

    items: list[DueReviewItem]
    total: int


class CompleteReviewRequest(BaseModel):
    """标记复习完成请求"""

    review_id: UUID


class ReviewPlanItem(BaseModel):
    """复习计划页条目"""

    id: UUID
    activity_id: UUID
    title: str
    subject_name: str | None = None
    space_name: str | None = None
    review_number: int
    scheduled_date: date
    status: str
    study_depth: str | None = None
    days_overdue: int = 0
    activity_time: datetime
    completed_at: datetime | None = None


class ReviewPlanStats(BaseModel):
    """复习计划页统计"""

    total: int
    today_pending: int
    today_completed: int
    streak: int


class ReviewPlanResponse(BaseModel):
    """复习计划页聚合响应"""

    stats: ReviewPlanStats
    items: list[ReviewPlanItem]
