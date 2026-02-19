"""艾宾浩斯遗忘曲线复习计划服务"""

import asyncio
import logging
import math
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update

from db.database import get_scoped_session
from db.models import ReviewSchedule

logger = logging.getLogger(__name__)

# ── 艾宾浩斯间隔配置 ──

BASE_INTERVALS = [1, 3, 7, 14, 30]  # 天

DEPTH_MULTIPLIERS = {
    "浅层浏览": 0.7,
    "中等理解": 1.0,
    "深入掌握": 1.5,
}

# GC 保护：防止 fire-and-forget task 被回收
_background_tasks: set[asyncio.Task] = set()


def calculate_review_dates(
    learning_date: date, study_depth: str | None
) -> list[tuple[int, date]]:
    """
    纯函数：根据学习日期和深度计算 5 个复习日期。

    Returns:
        [(review_number, scheduled_date), ...]
    """
    multiplier = DEPTH_MULTIPLIERS.get(study_depth or "", 1.0)
    results = []
    for i, base_days in enumerate(BASE_INTERVALS, start=1):
        adjusted = max(1, math.ceil(base_days * multiplier))
        review_date = learning_date + timedelta(days=adjusted)
        results.append((i, review_date))
    return results


async def generate_reviews_for_activity(
    user_id: UUID,
    activity_id: UUID,
    activity_date: date,
    study_depth: str | None,
    related_node_labels: list[str],
) -> None:
    """
    为一条学习活动生成复习计划。

    对每个 node_label：
      1. 去重合并：将该用户该节点所有已到期的 pending 复习标记为 completed
      2. 生成新计划：插入 5 条新的 ReviewSchedule 记录
    """
    if not related_node_labels:
        return

    review_dates = calculate_review_dates(activity_date, study_depth)

    async with get_scoped_session() as session:
        for node_label in related_node_labels:
            # 去重合并：标记旧的已到期 pending 为 completed
            await session.execute(
                update(ReviewSchedule)
                .where(
                    ReviewSchedule.user_id == user_id,
                    ReviewSchedule.node_label == node_label,
                    ReviewSchedule.status == "pending",
                    ReviewSchedule.scheduled_date <= activity_date,
                )
                .values(
                    status="completed",
                    completed_at=datetime.now(timezone.utc),
                    completed_by_activity_id=activity_id,
                )
            )

            # 生成新复习计划
            for review_number, scheduled_date in review_dates:
                schedule = ReviewSchedule(
                    user_id=user_id,
                    activity_id=activity_id,
                    node_label=node_label,
                    review_number=review_number,
                    scheduled_date=scheduled_date,
                    status="pending",
                    study_depth=study_depth,
                )
                session.add(schedule)

        await session.commit()
        total = len(related_node_labels) * len(review_dates)
        logger.info(
            f"Generated {total} review schedules for activity {activity_id} "
            f"(user={user_id}, nodes={len(related_node_labels)})"
        )


def schedule_review_generation(
    user_id: UUID,
    activity_id: UUID,
    activity_date: date,
    study_depth: str | None,
    related_node_labels: list[str],
) -> None:
    """Fire-and-forget 包装器，在后台生成复习计划。"""

    async def _run() -> None:
        try:
            await generate_reviews_for_activity(
                user_id=user_id,
                activity_id=activity_id,
                activity_date=activity_date,
                study_depth=study_depth,
                related_node_labels=related_node_labels,
            )
        except Exception as e:
            logger.error(
                f"Background review generation failed for activity {activity_id}: {e}",
                exc_info=True,
            )

    task = asyncio.create_task(_run())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def get_reviews_for_activity(
    user_id: UUID, activity_id: UUID
) -> list[ReviewSchedule]:
    """查询某活动的所有复习计划。"""
    async with get_scoped_session() as session:
        result = await session.execute(
            select(ReviewSchedule)
            .where(
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.activity_id == activity_id,
            )
            .order_by(ReviewSchedule.node_label, ReviewSchedule.review_number)
        )
        rows = result.scalars().all()
        # Eagerly access attributes before session closes
        for r in rows:
            _ = (
                r.id,
                r.node_label,
                r.review_number,
                r.scheduled_date,
                r.status,
                r.completed_at,
                r.study_depth,
            )
        return list(rows)


async def get_due_reviews(user_id: UUID, limit: int = 20) -> list[ReviewSchedule]:
    """查询到期/逾期待复习项（scheduled_date <= today, status=pending）。"""
    today = datetime.now(timezone.utc).date()
    async with get_scoped_session() as session:
        result = await session.execute(
            select(ReviewSchedule)
            .where(
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.status == "pending",
                ReviewSchedule.scheduled_date <= today,
            )
            .order_by(ReviewSchedule.scheduled_date.asc())
            .limit(limit)
        )
        rows = result.scalars().all()
        for r in rows:
            _ = (
                r.id,
                r.activity_id,
                r.node_label,
                r.review_number,
                r.scheduled_date,
                r.study_depth,
            )
        return list(rows)


async def complete_review(user_id: UUID, review_id: UUID) -> bool:
    """手动标记复习完成。Atomic UPDATE to avoid race conditions."""
    async with get_scoped_session() as session:
        result = await session.execute(
            update(ReviewSchedule)
            .where(
                ReviewSchedule.id == review_id,
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.status == "pending",
            )
            .values(
                status="completed",
                completed_at=datetime.now(timezone.utc),
            )
        )
        if result.rowcount == 0:
            return False
        await session.commit()
        logger.info(f"Manually completed review {review_id} for user {user_id}")
        return True
