"""Review schedule API 路由"""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from auth.dependencies import CurrentUser
from review.schemas import (
    ActivityReviewsResponse,
    CompleteReviewRequest,
    DueReviewItem,
    DueReviewsResponse,
    ReviewScheduleItem,
)
from review.service import (
    complete_review,
    get_due_reviews,
    get_due_reviews_total,
    get_reviews_for_activity,
)

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/activity/{activity_id}", response_model=ActivityReviewsResponse)
async def get_activity_reviews(
    activity_id: UUID,
    user: CurrentUser,
):
    """获取某活动的复习计划（详情弹窗用）"""
    reviews = await get_reviews_for_activity(user.id, activity_id)
    return ActivityReviewsResponse(
        activity_id=activity_id,
        items=[ReviewScheduleItem.model_validate(r) for r in reviews],
    )


@router.get("/due", response_model=DueReviewsResponse)
async def get_due_reviews_endpoint(
    user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
):
    """获取到期/逾期复习项（items 受 limit 限制，total 为去重后的学习事件总数）。"""
    reviews = await get_due_reviews(user.id, limit)
    total = await get_due_reviews_total(user.id)
    today = datetime.now(timezone.utc).date()
    items = []
    for r in reviews:
        days_overdue = (today - r.scheduled_date).days
        items.append(
            DueReviewItem(
                id=r.id,
                activity_id=r.activity_id,
                node_label=r.node_label,
                review_number=r.review_number,
                scheduled_date=r.scheduled_date,
                study_depth=r.study_depth,
                days_overdue=max(0, days_overdue),
            )
        )
    return DueReviewsResponse(items=items, total=total)


@router.post("/complete")
async def complete_review_endpoint(
    body: CompleteReviewRequest,
    user: CurrentUser,
):
    """手动标记复习完成"""
    success = await complete_review(user.id, body.review_id)
    if not success:
        raise HTTPException(status_code=404, detail="复习记录未找到或已完成")
    return {"success": True}
