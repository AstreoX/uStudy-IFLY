"""艾宾浩斯遗忘曲线复习计划服务"""

import asyncio
import logging
import math
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select, update

from db.database import get_scoped_session
from db.models import ReviewSchedule, StudyActivityLog

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
) -> None:
    """为一条学习活动生成 5 条复习计划（按学习事件粒度）。"""
    review_dates = calculate_review_dates(activity_date, study_depth)

    async with get_scoped_session() as session:
        for review_number, scheduled_date in review_dates:
            schedule = ReviewSchedule(
                user_id=user_id,
                activity_id=activity_id,
                node_label=None,
                review_number=review_number,
                scheduled_date=scheduled_date,
                status="pending",
                study_depth=study_depth,
            )
            session.add(schedule)

        await session.commit()
        logger.info(
            f"Generated {len(review_dates)} review schedules for activity {activity_id} "
            f"(user={user_id})"
        )


def schedule_review_generation(
    user_id: UUID,
    activity_id: UUID,
    activity_date: date,
    study_depth: str | None,
) -> None:
    """Fire-and-forget 包装器，在后台生成复习计划。"""

    async def _run() -> None:
        try:
            await generate_reviews_for_activity(
                user_id=user_id,
                activity_id=activity_id,
                activity_date=activity_date,
                study_depth=study_depth,
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
            .order_by(ReviewSchedule.review_number)
        )
        rows = result.scalars().all()
        # Eagerly access attributes before session closes
        for r in rows:
            _ = (
                r.id,
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
                r.review_number,
                r.scheduled_date,
                r.study_depth,
            )
        return list(rows)


async def get_due_reviews_total(user_id: UUID) -> int:
    """查询到期/逾期待复习学习事件总数（按 activity_id 去重）。"""
    today = datetime.now(timezone.utc).date()
    async with get_scoped_session() as session:
        result = await session.execute(
            select(func.count(func.distinct(ReviewSchedule.activity_id)))
            .select_from(ReviewSchedule)
            .where(
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.status == "pending",
                ReviewSchedule.scheduled_date <= today,
            )
        )
        return int(result.scalar() or 0)


async def get_due_reviews_count_by_space(user_id: UUID, space_id: UUID) -> int:
    """查询某学习空间到期/逾期待复习项数量（按 activity_id 去重）。"""
    today = datetime.now(timezone.utc).date()
    async with get_scoped_session() as session:
        result = await session.execute(
            select(func.count(func.distinct(ReviewSchedule.activity_id)))
            .select_from(ReviewSchedule)
            .join(
                StudyActivityLog,
                ReviewSchedule.activity_id == StudyActivityLog.id,
            )
            .where(
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.status == "pending",
                ReviewSchedule.scheduled_date <= today,
                StudyActivityLog.space_id == space_id,
            )
        )
        return int(result.scalar() or 0)


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


async def get_due_reviews_by_space(
    user_id: UUID, space_id: UUID, limit: int = 10
) -> list[tuple[ReviewSchedule, StudyActivityLog]]:
    """查询某学习空间到期/逾期待复习项，并按 activity_id 去重。

    Returns:
        List of (ReviewSchedule, StudyActivityLog) tuples.
    """
    today = datetime.now(timezone.utc).date()
    async with get_scoped_session() as session:
        ranked_due_reviews = (
            select(
                ReviewSchedule.id.label("review_id"),
                func.row_number()
                .over(
                    partition_by=ReviewSchedule.activity_id,
                    order_by=(
                        ReviewSchedule.scheduled_date.asc(),
                        ReviewSchedule.review_number.asc(),
                        ReviewSchedule.id.asc(),
                    ),
                )
                .label("rn"),
            )
            .join(
                StudyActivityLog,
                ReviewSchedule.activity_id == StudyActivityLog.id,
            )
            .where(
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.status == "pending",
                ReviewSchedule.scheduled_date <= today,
                StudyActivityLog.space_id == space_id,
            )
            .subquery()
        )

        result = await session.execute(
            select(ReviewSchedule, StudyActivityLog)
            .join(
                ranked_due_reviews,
                ReviewSchedule.id == ranked_due_reviews.c.review_id,
            )
            .join(
                StudyActivityLog,
                ReviewSchedule.activity_id == StudyActivityLog.id,
            )
            .where(ranked_due_reviews.c.rn == 1)
            .order_by(ReviewSchedule.scheduled_date.asc())
            .limit(limit)
        )
        rows = result.all()
        # Eagerly access attributes before session closes
        for r, a in rows:
            _ = (
                r.id,
                r.activity_id,
                r.review_number,
                r.scheduled_date,
                r.study_depth,
                a.title,
                a.related_node_labels,
            )
        return list(rows)


async def complete_reviews_by_activity(user_id: UUID, activity_id: UUID) -> int:
    """按学习事件批量标记到期 pending 复习为 completed。返回受影响行数。"""
    today = datetime.now(timezone.utc).date()
    async with get_scoped_session() as session:
        result = await session.execute(
            update(ReviewSchedule)
            .where(
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.activity_id == activity_id,
                ReviewSchedule.status == "pending",
                ReviewSchedule.scheduled_date <= today,
            )
            .values(
                status="completed",
                completed_at=datetime.now(timezone.utc),
            )
        )
        count = result.rowcount
        await session.commit()
        if count > 0:
            logger.info(
                f"Completed {count} due reviews for activity {activity_id} (user={user_id})"
            )
        return count


def format_due_reviews_for_prompt(
    reviews: list[tuple[ReviewSchedule, StudyActivityLog]],
) -> str:
    """将到期复习列表格式化为 prompt 注入文本。

    每行格式: - {activity_title} [{study_depth}] — 第N次复习（逾期X天/今日到期）
    """
    if not reviews:
        return ""

    today = datetime.now(timezone.utc).date()
    lines = []
    for r, activity in reviews:
        depth_tag = f" [{r.study_depth}]" if r.study_depth else ""
        overdue_days = (today - r.scheduled_date).days
        if overdue_days > 0:
            urgency = f"逾期{overdue_days}天"
        else:
            urgency = "今日到期"
        lines.append(
            f"- {activity.title}{depth_tag} — 第{r.review_number}次复习（{urgency}）"
        )
    return "\n".join(lines)
