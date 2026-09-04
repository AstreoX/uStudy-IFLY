"""SM-2 自适应间隔复习计划服务"""

import asyncio
import logging
import math
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, cast, func, or_, select, update
from sqlalchemy.types import Date as SQLDate

from db.database import get_scoped_session
from db.models import ReviewSchedule, Space, StudyActivityLog
from review.schemas import ReviewPlanItem, ReviewPlanResponse, ReviewPlanStats
from review.sm2 import score_to_quality, should_graduate, sm2_next_review

logger = logging.getLogger(__name__)

# ── 首次复习间隔的深度乘子 ──

DEPTH_MULTIPLIERS = {
    "浅层浏览": 0.7,
    "中等理解": 1.0,
    "深入掌握": 1.5,
}

# SM-2 默认初始值
DEFAULT_EASE_FACTOR = 2.5

# GC 保护：防止 fire-and-forget task 被回收
_background_tasks: set[asyncio.Task] = set()


def calculate_first_interval(study_depth: str | None) -> int:
    """根据学习深度计算首次复习间隔天数。"""
    multiplier = DEPTH_MULTIPLIERS.get(study_depth or "", 1.0)
    return max(1, math.ceil(1 * multiplier))


async def generate_reviews_for_activity(
    user_id: UUID,
    activity_id: UUID,
    activity_date: date,
    study_depth: str | None,
) -> None:
    """为一条学习活动生成首条复习计划（SM-2：后续复习在完成时动态生成）。"""
    first_interval = calculate_first_interval(study_depth)
    scheduled_date = activity_date + timedelta(days=first_interval)

    async with get_scoped_session() as session:
        schedule = ReviewSchedule(
            user_id=user_id,
            activity_id=activity_id,
            node_label=None,
            review_number=1,
            scheduled_date=scheduled_date,
            status="pending",
            study_depth=study_depth,
            ease_factor=DEFAULT_EASE_FACTOR,
            interval_days=first_interval,
        )
        session.add(schedule)
        await session.commit()
        logger.info(
            f"Generated first review schedule for activity {activity_id} "
            f"(user={user_id}, interval={first_interval}d)"
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
    """手动标记复习完成，使用中性 quality=3 生成下一条复习。"""
    async with get_scoped_session() as session:
        result = await session.execute(
            select(ReviewSchedule).where(
                ReviewSchedule.id == review_id,
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.status == "pending",
            )
        )
        review = result.scalar_one_or_none()
        if not review:
            return False

        now = datetime.now(timezone.utc)
        quality = 3  # 手动完成视为中性

        # 标记完成
        review.status = "completed"
        review.completed_at = now
        review.quality_score = quality

        # 生成下一条复习（除非毕业）
        if not should_graduate(review.review_number, quality):
            next_interval, new_ef = sm2_next_review(
                review.review_number, review.ease_factor, quality, review.interval_days,
            )
            # SM-2: 失败 (quality < 3) 时重置 review_number 为 1
            next_number = 1 if quality < 3 else review.review_number + 1
            next_schedule = ReviewSchedule(
                user_id=user_id,
                activity_id=review.activity_id,
                node_label=review.node_label,
                review_number=next_number,
                scheduled_date=now.date() + timedelta(days=next_interval),
                status="pending",
                study_depth=review.study_depth,
                ease_factor=new_ef,
                interval_days=next_interval,
            )
            session.add(next_schedule)

        await session.commit()
        logger.info(f"Manually completed review {review_id} for user {user_id}")

        from activity.suggestion import invalidate_suggestion_cache
        invalidate_suggestion_cache(user_id)

        return True


async def complete_review_with_quiz_score(
    user_id: UUID,
    review_id: UUID,
    quiz_score: int,
    quiz_total: int,
) -> ReviewSchedule | None:
    """根据测试题成绩完成复习并动态生成下一条。

    Returns:
        新生成的 ReviewSchedule，如果毕业则返回 None。
    """
    async with get_scoped_session() as session:
        result = await session.execute(
            select(ReviewSchedule).where(
                ReviewSchedule.id == review_id,
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.status == "pending",
            )
        )
        review = result.scalar_one_or_none()
        if not review:
            return None

        now = datetime.now(timezone.utc)
        quality = score_to_quality(quiz_score, quiz_total)

        # 标记完成
        review.status = "completed"
        review.completed_at = now
        review.quality_score = quality

        # 生成下一条复习（除非毕业）
        next_schedule = None
        if not should_graduate(review.review_number, quality):
            next_interval, new_ef = sm2_next_review(
                review.review_number, review.ease_factor, quality, review.interval_days,
            )
            # SM-2: 失败 (quality < 3) 时重置 review_number 为 1
            next_number = 1 if quality < 3 else review.review_number + 1
            next_schedule = ReviewSchedule(
                user_id=user_id,
                activity_id=review.activity_id,
                node_label=review.node_label,
                review_number=next_number,
                scheduled_date=now.date() + timedelta(days=next_interval),
                status="pending",
                study_depth=review.study_depth,
                ease_factor=new_ef,
                interval_days=next_interval,
            )
            session.add(next_schedule)
            logger.info(
                f"SM-2 review {review_id}: q={quality}, ef={new_ef:.2f}, "
                f"next_interval={next_interval}d, next_number={next_number}"
            )
        else:
            logger.info(
                f"Review graduated: activity {review.activity_id} after "
                f"{review.review_number} reviews (user={user_id})"
            )

        await session.commit()

        from activity.suggestion import invalidate_suggestion_cache
        invalidate_suggestion_cache(user_id)

        return next_schedule


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


async def get_due_reviews_all_spaces(
    user_id: UUID, limit: int = 20
) -> list[tuple[ReviewSchedule, StudyActivityLog, str | None]]:
    """查询用户所有学习空间中到期/逾期待复习项，按 activity_id 去重。

    Returns:
        List of (ReviewSchedule, StudyActivityLog, space_name) tuples.
        space_name 可能为 None（活动未关联空间时）。
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
            )
            .subquery()
        )

        result = await session.execute(
            select(ReviewSchedule, StudyActivityLog, Space.name)
            .join(
                ranked_due_reviews,
                ReviewSchedule.id == ranked_due_reviews.c.review_id,
            )
            .join(
                StudyActivityLog,
                ReviewSchedule.activity_id == StudyActivityLog.id,
            )
            .outerjoin(
                Space,
                StudyActivityLog.space_id == Space.id,
            )
            .where(ranked_due_reviews.c.rn == 1)
            .order_by(ReviewSchedule.scheduled_date.asc())
            .limit(limit)
        )
        rows = result.all()
        # Eagerly access attributes before session closes
        for r, a, space_name in rows:
            _ = (
                r.id,
                r.activity_id,
                r.review_number,
                r.scheduled_date,
                r.study_depth,
                a.title,
                a.related_node_labels,
                space_name,
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


async def get_plan_items(
    user_id: UUID,
) -> list[tuple[ReviewSchedule, StudyActivityLog, str | None]]:
    """复习计划页条目：今日到期/逾期的 pending + 今日已完成。"""
    today = datetime.now(timezone.utc).date()
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)

    async with get_scoped_session() as session:
        result = await session.execute(
            select(ReviewSchedule, StudyActivityLog, Space.name)
            .join(
                StudyActivityLog,
                ReviewSchedule.activity_id == StudyActivityLog.id,
            )
            .outerjoin(
                Space,
                StudyActivityLog.space_id == Space.id,
            )
            .where(
                ReviewSchedule.user_id == user_id,
                or_(
                    and_(
                        ReviewSchedule.status == "pending",
                        ReviewSchedule.scheduled_date <= today,
                    ),
                    and_(
                        ReviewSchedule.status == "completed",
                        ReviewSchedule.completed_at >= today_start,
                        ReviewSchedule.completed_at < today_end,
                    ),
                ),
            )
            .order_by(
                ReviewSchedule.scheduled_date.asc(),
                ReviewSchedule.review_number.asc(),
                ReviewSchedule.id.asc(),
            )
        )
        rows = result.all()
        # Eagerly access attributes before session closes
        for r, a, space_name in rows:
            _ = (
                r.id,
                r.activity_id,
                r.review_number,
                r.scheduled_date,
                r.status,
                r.completed_at,
                r.study_depth,
                a.title,
                a.subject_name,
                a.activity_time,
                space_name,
            )
        return list(rows)


async def get_plan_stats(user_id: UUID) -> ReviewPlanStats:
    """复习计划页统计：总数 / 今日待复习 / 今日已完成 / 连续天数。"""
    today = datetime.now(timezone.utc).date()
    today_start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)

    async with get_scoped_session() as session:
        total_res = await session.execute(
            select(func.count(ReviewSchedule.id)).where(
                ReviewSchedule.user_id == user_id,
            )
        )
        total = int(total_res.scalar() or 0)

        pending_res = await session.execute(
            select(func.count(ReviewSchedule.id)).where(
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.status == "pending",
                ReviewSchedule.scheduled_date <= today,
            )
        )
        today_pending = int(pending_res.scalar() or 0)

        completed_res = await session.execute(
            select(func.count(ReviewSchedule.id)).where(
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.status == "completed",
                ReviewSchedule.completed_at >= today_start,
                ReviewSchedule.completed_at < today_end,
            )
        )
        today_completed = int(completed_res.scalar() or 0)

        # 取最近 60 天内有完成记录的天（去重），Python 侧计算连续天数
        window_start = today_start - timedelta(days=60)
        days_res = await session.execute(
            select(cast(ReviewSchedule.completed_at, SQLDate))
            .where(
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.status == "completed",
                ReviewSchedule.completed_at >= window_start,
            )
            .distinct()
        )
        completed_days = {row[0] for row in days_res.all() if row[0] is not None}

        streak = 0
        cursor = today
        while cursor in completed_days:
            streak += 1
            cursor = cursor - timedelta(days=1)

    return ReviewPlanStats(
        total=total,
        today_pending=today_pending,
        today_completed=today_completed,
        streak=streak,
    )


async def get_review_plan(user_id: UUID) -> ReviewPlanResponse:
    """聚合复习计划页数据（统计 + 条目）。"""
    stats = await get_plan_stats(user_id)
    rows = await get_plan_items(user_id)

    today = datetime.now(timezone.utc).date()
    items: list[ReviewPlanItem] = []
    for r, activity, space_name in rows:
        days_overdue = (today - r.scheduled_date).days
        items.append(
            ReviewPlanItem(
                id=r.id,
                activity_id=r.activity_id,
                title=activity.title,
                subject_name=activity.subject_name,
                space_name=space_name,
                review_number=r.review_number,
                scheduled_date=r.scheduled_date,
                status=r.status,
                study_depth=r.study_depth,
                days_overdue=max(0, days_overdue),
                activity_time=activity.activity_time,
                completed_at=r.completed_at,
            )
        )

    return ReviewPlanResponse(stats=stats, items=items)


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
