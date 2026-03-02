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

    # Batch query: review status per activity
    items = [ActivityTimelineItem.model_validate(a) for a in activities]
    activity_ids = [a.id for a in activities]
    next_pending_map: dict = {}
    last_completed_map: dict = {}
    if activity_ids:
        # Query 1: next pending review (earliest scheduled_date per activity)
        pending_ranked = (
            select(
                ReviewSchedule.activity_id,
                ReviewSchedule.scheduled_date,
                ReviewSchedule.review_number,
                func.row_number()
                .over(
                    partition_by=ReviewSchedule.activity_id,
                    order_by=(
                        ReviewSchedule.scheduled_date.asc(),
                        ReviewSchedule.review_number.asc(),
                    ),
                )
                .label("rn"),
            )
            .where(
                ReviewSchedule.activity_id.in_(activity_ids),
                ReviewSchedule.status == "pending",
            )
            .subquery()
        )
        next_pending_result = await db.execute(
            select(
                pending_ranked.c.activity_id,
                pending_ranked.c.scheduled_date,
                pending_ranked.c.review_number,
            ).where(pending_ranked.c.rn == 1)
        )
        next_pending_map = {
            row.activity_id: (row.scheduled_date, row.review_number)
            for row in next_pending_result
        }

        # Query 2: most recently completed review per activity
        completed_ranked = (
            select(
                ReviewSchedule.activity_id,
                ReviewSchedule.completed_at,
                ReviewSchedule.review_number,
                func.row_number()
                .over(
                    partition_by=ReviewSchedule.activity_id,
                    order_by=ReviewSchedule.completed_at.desc(),
                )
                .label("rn"),
            )
            .where(
                ReviewSchedule.activity_id.in_(activity_ids),
                ReviewSchedule.status == "completed",
                ReviewSchedule.completed_at.isnot(None),
            )
            .subquery()
        )
        last_completed_result = await db.execute(
            select(
                completed_ranked.c.activity_id,
                completed_ranked.c.completed_at,
                completed_ranked.c.review_number,
            ).where(completed_ranked.c.rn == 1)
        )
        last_completed_map = {
            row.activity_id: (row.completed_at, row.review_number)
            for row in last_completed_result
        }

    for item in items:
        pending = next_pending_map.get(item.id)
        if pending:
            item.next_review_date, item.next_review_number = pending

        completed = last_completed_map.get(item.id)
        if completed:
            item.last_completed_at, item.last_completed_review_number = completed

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
