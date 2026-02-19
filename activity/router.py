"""Activity API 路由"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from activity.schemas import (
    ActivityTimelineItem,
    ActivityTimelineResponse,
    StudySuggestionResponse,
)
from activity.suggestion import get_ai_suggestion
from auth.dependencies import CurrentUser
from db.database import get_db
from db.models import ReviewSchedule, StudyActivityLog

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("/timeline", response_model=ActivityTimelineResponse)
async def get_activity_timeline(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    space_id: UUID | None = Query(None),
    activity_type: str | None = Query(None),
):
    """获取学习活动时间线"""
    # 构建查询条件
    conditions = [StudyActivityLog.user_id == user.id]
    if space_id:
        conditions.append(StudyActivityLog.space_id == space_id)
    if activity_type:
        conditions.append(StudyActivityLog.activity_type == activity_type)

    # 查询总数
    count_result = await db.execute(
        select(func.count()).select_from(StudyActivityLog).where(*conditions)
    )
    total = count_result.scalar() or 0

    # 查询分页数据
    offset = (page - 1) * limit
    result = await db.execute(
        select(StudyActivityLog)
        .where(*conditions)
        .order_by(StudyActivityLog.activity_time.desc())
        .offset(offset)
        .limit(limit)
    )
    activities = result.scalars().all()

    # Batch query: next pending review date per activity
    items = [ActivityTimelineItem.model_validate(a) for a in activities]
    activity_ids = [a.id for a in activities]
    review_date_map: dict = {}
    if activity_ids:
        review_result = await db.execute(
            select(
                ReviewSchedule.activity_id,
                func.min(ReviewSchedule.scheduled_date).label("next_review_date"),
            )
            .where(
                ReviewSchedule.activity_id.in_(activity_ids),
                ReviewSchedule.status == "pending",
            )
            .group_by(ReviewSchedule.activity_id)
        )
        review_date_map = {
            row.activity_id: row.next_review_date for row in review_result
        }

    for item in items:
        item.next_review_date = review_date_map.get(item.id)

    return ActivityTimelineResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
    )


@router.get("/suggestion", response_model=StudySuggestionResponse)
async def get_study_suggestion(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    refresh: bool = Query(False),
):
    """AI 驱动的学习建议：根据近期活动和待复习项生成"""
    result = await get_ai_suggestion(user.id, db, force_refresh=refresh)
    return StudySuggestionResponse(**result)
