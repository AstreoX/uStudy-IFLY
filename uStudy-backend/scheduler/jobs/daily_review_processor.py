"""每日复习处理定时任务

每日 08:00 北京时间执行：
1. 收集所有用户的到期复习事项
2. 按 (user, space) 分组
3. AI 规划 + 生成复习测试题
4. 创建站内复习提醒
"""

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError

from db.database import AsyncSessionLocal, get_scoped_session
from db.models import (
    AgentTask,
    AgentTaskStatus,
    AgentTaskType,
    DailyStudyRecord,
    DifficultyLevel,
    Quiz,
    ReviewSchedule,
    Space,
    StudyActivityLog,
    User,
)
from scheduler.models import SchedulerState

logger = logging.getLogger(__name__)

JOB_ID = "daily_review_processor"
BEIJING_TZ = ZoneInfo("Asia/Shanghai")

# 并发控制：同时生成的测试题任务数
MAX_CONCURRENT_GENERATIONS = 5


def _stable_lock_key(*parts: str) -> int:
    """生成跨进程稳定的 advisory lock key（不受 PYTHONHASHSEED 影响）。"""
    raw = ":".join(parts).encode()
    return int(hashlib.md5(raw).hexdigest()[:8], 16) & 0x7FFFFFFF


@dataclass
class ReviewItem:
    """单条到期复习事项。"""
    review_id: UUID
    activity_id: UUID
    title: str
    study_depth: str | None
    review_number: int
    scheduled_date: Any
    overdue_days: int


@dataclass
class SpaceReviewGroup:
    """某用户某空间下的一组到期复习。"""
    space_id: UUID
    space_name: str
    review_mode: int
    learning_preferences: dict | None
    reviews: list[ReviewItem] = field(default_factory=list)


@dataclass
class UserReviewData:
    """某用户的全部到期复习数据。"""
    user_id: UUID
    user_email: str
    nickname: str
    space_groups: list[SpaceReviewGroup] = field(default_factory=list)


def _coerce_date(value: date | datetime | None) -> date | None:
    """统一转为 date，datetime 按 UTC 日期处理。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.date()
        return value.astimezone(timezone.utc).date()
    return value


def _resolve_last_activity_date(*activity_dates: date | datetime | None) -> date | None:
    """取多个活跃日期中的最新值。"""
    normalized = [d for d in (_coerce_date(v) for v in activity_dates) if d is not None]
    return max(normalized) if normalized else None


async def process_daily_reviews() -> None:
    """每日复习处理主入口。

    遵循 3-phase + SchedulerState 防重复模式。
    """
    logger.info("Starting daily review processor")

    today_beijing = datetime.now(BEIJING_TZ).date()
    today_utc = datetime.now(timezone.utc).date()

    try:
        # Phase 0: 原子性抢占 — 在一个短事务内完成互斥 + 日期检查 + 标记
        # 使用 pg_try_advisory_xact_lock（事务级，commit 时自动释放），不长期占连接
        lock_key = _stable_lock_key(JOB_ID)
        async with get_scoped_session() as db:
            lock_result = await db.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": lock_key},
            )
            if not lock_result.scalar():
                logger.info("Another worker is running daily_review_processor, skipping")
                return

            check_result = await db.execute(
                select(SchedulerState.last_run_date).where(
                    SchedulerState.job_id == JOB_ID
                )
            )
            existing_date = check_result.scalar_one_or_none()
            if existing_date is not None and existing_date == today_beijing:
                logger.info("Daily review already processed today (%s), skipping", today_beijing)
                return

            # 立即标记今天已处理（占位），防止其他 worker 重复执行
            row_exists = existing_date is not None
            if row_exists:
                await db.execute(
                    update(SchedulerState)
                    .where(SchedulerState.job_id == JOB_ID)
                    .values(last_run_date=today_beijing, last_run_at=func.now())
                )
            else:
                db.add(SchedulerState(job_id=JOB_ID, last_run_date=today_beijing))

            try:
                await db.commit()  # 提交占位 + 释放 xact lock + 归还连接
            except IntegrityError:
                logger.info("Another worker already claimed daily_review_processor for today")
                await db.rollback()
                return

        # 此后无 DB session 被持有 — 安全地执行长时间 LLM 任务

        # Phase 1: 收集数据
        user_reviews = await _gather_review_data(today_utc)
        if not user_reviews:
            logger.info("No users with due reviews today")
            await _check_inactivity(today_utc)
            return

        logger.info("Found %d users with due reviews", len(user_reviews))

        # Phase 2: 生成测试题（带并发控制）
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_GENERATIONS)
        generation_results: dict[UUID, list[dict]] = {}  # user_id -> [{space_name, topics, quiz_id, due_count}]

        async def process_user(user_data: UserReviewData) -> None:
            user_summaries = []
            for group in user_data.space_groups:
                summary = {
                    "space_name": group.space_name,
                    "space_id": str(group.space_id),
                    "topics": [r.title for r in group.reviews[:5]],
                    "due_count": len(group.reviews),
                    "quiz_id": None,
                }

                if group.review_mode >= 2:
                    async with semaphore:
                        quiz_id = await _generate_review_quiz(
                            user_data.user_id, group,
                        )
                        summary["quiz_id"] = str(quiz_id) if quiz_id else None

                user_summaries.append(summary)
            generation_results[user_data.user_id] = user_summaries

            from activity.suggestion import invalidate_suggestion_cache
            invalidate_suggestion_cache(user_data.user_id)

        tasks = [process_user(ud) for ud in user_reviews]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for ud, result in zip(user_reviews, results):
            if isinstance(result, BaseException):
                logger.error(
                    "process_user failed for user=%s: %s", ud.user_id, result,
                )

        # Phase 3: 所有测试题生成完成后，统一发送站内通知
        await _send_notifications(user_reviews, generation_results)

        logger.info("Daily review processor completed successfully")

    except Exception:
        logger.exception("Error in daily review processor")


async def _gather_review_data(today: Any) -> list[UserReviewData]:
    """收集所有用户的到期复习数据。"""
    async with get_scoped_session() as db:
        # 查询到期复习 JOIN 活动 + 空间 + 用户
        stmt = (
            select(
                ReviewSchedule.id,
                ReviewSchedule.activity_id,
                ReviewSchedule.review_number,
                ReviewSchedule.scheduled_date,
                ReviewSchedule.study_depth,
                StudyActivityLog.title,
                StudyActivityLog.space_id,
                Space.name.label("space_name"),
                Space.review_mode,
                Space.learning_preferences,
                User.id.label("user_id"),
                User.email.label("user_email"),
                User.nickname,
            )
            .join(StudyActivityLog, ReviewSchedule.activity_id == StudyActivityLog.id)
            .join(Space, StudyActivityLog.space_id == Space.id)
            .join(User, ReviewSchedule.user_id == User.id)
            .where(
                ReviewSchedule.status == "pending",
                ReviewSchedule.scheduled_date <= today,
                Space.review_mode > 0,
            )
            .order_by(User.id, Space.id, ReviewSchedule.scheduled_date)
        )

        result = await db.execute(stmt)
        rows = result.all()

    # 组装为结构化数据
    users_map: dict[UUID, UserReviewData] = {}
    spaces_map: dict[tuple[UUID, UUID], SpaceReviewGroup] = {}

    for row in rows:
        user_id = row.user_id
        space_id = row.space_id

        if user_id not in users_map:
            users_map[user_id] = UserReviewData(
                user_id=user_id,
                user_email=row.user_email,
                nickname=row.nickname or "同学",
            )

        key = (user_id, space_id)
        if key not in spaces_map:
            group = SpaceReviewGroup(
                space_id=space_id,
                space_name=row.space_name,
                review_mode=row.review_mode,
                learning_preferences=row.learning_preferences,
            )
            spaces_map[key] = group
            users_map[user_id].space_groups.append(group)

        overdue_days = (today - row.scheduled_date).days if hasattr(row.scheduled_date, '__sub__') else 0
        spaces_map[key].reviews.append(ReviewItem(
            review_id=row.id,
            activity_id=row.activity_id,
            title=row.title or "未命名活动",
            study_depth=row.study_depth,
            review_number=row.review_number,
            scheduled_date=row.scheduled_date,
            overdue_days=max(0, overdue_days),
        ))

    return list(users_map.values())


async def _generate_review_quiz(
    user_id: UUID,
    group: SpaceReviewGroup,
) -> UUID | None:
    """为一个 (user, space) 生成复习测试题。

    两级 Agent：Planner → TestGenerationAgent
    """
    from agents.review_quiz_planner import ReviewQuizPlannerAgent
    from agents.test_generation_agent import TestGenerationAgent

    try:
        # 纵深防御：短事务内检查 + advisory lock 防并发
        pair_key = _stable_lock_key(str(user_id), str(group.space_id))
        async with get_scoped_session() as check_db:
            lock_ok = await check_db.execute(
                text("SELECT pg_try_advisory_xact_lock(:key)"),
                {"key": pair_key},
            )
            if not lock_ok.scalar():
                logger.info(
                    "Another worker generating quiz for user=%s space=%s, skipping",
                    user_id, group.space_id,
                )
                return None

            existing = await check_db.execute(
                select(func.count(ReviewSchedule.id))
                .select_from(ReviewSchedule)
                .join(StudyActivityLog, ReviewSchedule.activity_id == StudyActivityLog.id)
                .where(
                    ReviewSchedule.user_id == user_id,
                    ReviewSchedule.review_quiz_id.isnot(None),
                    ReviewSchedule.status == "pending",
                    StudyActivityLog.space_id == group.space_id,
                )
            )
            if (existing.scalar() or 0) > 0:
                logger.info(
                    "Skipping quiz gen for user=%s space=%s: existing pending review quiz",
                    user_id, group.space_id,
                )
                return None
            await check_db.commit()  # 释放 xact lock + 连接

        # 第 1 级：Planner（纯 LLM 调用，无 DB 连接占用）
        planner = ReviewQuizPlannerAgent()
        review_items = [
            {
                "title": r.title,
                "study_depth": r.study_depth,
                "overdue_days": r.overdue_days,
                "review_number": r.review_number,
            }
            for r in group.reviews
        ]

        plan = await planner.plan(
            space_name=group.space_name,
            learning_preferences=group.learning_preferences,
            review_items=review_items,
            user_id=user_id,
            space_id=group.space_id,
            billable=False,
        )

        # 第 2 级：TestGenerationAgent
        async with AsyncSessionLocal() as session:
            # 创建 AgentTask
            task = AgentTask(
                user_id=user_id,
                space_id=group.space_id,
                task_type=AgentTaskType.GENERATE_REVIEW_QUIZ,
                status=AgentTaskStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
                input_data={
                    "topic": plan["topic"],
                    "difficulty_level": plan["difficulty_level"],
                    "test_struct": plan["test_struct"],
                    "focus_areas": plan.get("focus_areas", []),
                    "reasoning": plan.get("reasoning", ""),
                    "source": "daily_review_processor",
                },
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)

            # 创建 Quiz
            quiz = Quiz(
                space_id=group.space_id,
                agent_task_id=task.id,
                creator_user_id=user_id,
                visibility="shared",
                title=f"复习测试: {plan['topic'][:150]}",
                topic=plan["topic"],
                difficulty=DifficultyLevel(plan["difficulty_level"]),
                total_questions=0,
                is_review_quiz=True,
            )
            session.add(quiz)
            await session.commit()
            await session.refresh(quiz)

            # 执行生成
            agent = TestGenerationAgent(session)
            expected, actual, debug_logs = await agent.generate(
                quiz_id=quiz.id,
                topic=plan["topic"],
                difficulty=plan["difficulty_level"],
                test_struct=plan["test_struct"],
                user_id=user_id,
                space_id=group.space_id,
                billable=False,
            )

            # 更新 AgentTask 为 done
            await session.execute(
                update(AgentTask)
                .where(AgentTask.id == task.id)
                .values(
                    status=AgentTaskStatus.DONE,
                    completed_at=datetime.now(timezone.utc),
                    output_data={
                        "quiz_id": str(quiz.id),
                        "expected_count": expected,
                        "question_count": actual,
                        "plan": plan,
                    },
                )
            )
            await session.commit()

            # 关联 quiz 到 review schedules
            review_ids = [r.review_id for r in group.reviews]
            if review_ids:
                await session.execute(
                    update(ReviewSchedule)
                    .where(ReviewSchedule.id.in_(review_ids))
                    .values(review_quiz_id=quiz.id)
                )
                await session.commit()

            logger.info(
                "Generated review quiz: user=%s, space=%s, quiz=%s, questions=%d",
                user_id, group.space_id, quiz.id, actual,
            )
            return quiz.id

    except Exception:
        logger.exception(
            "Failed to generate review quiz for user=%s space=%s",
            user_id, group.space_id,
        )
        return None


async def _send_notifications(
    user_reviews: list[UserReviewData],
    generation_results: dict[UUID, list[dict]],
) -> None:
    """所有测试题生成完成后，为每个用户发送一条汇总通知。"""
    from db.models import NotificationType
    from notifications.service import NotificationService

    for user_data in user_reviews:
        summaries = generation_results.get(user_data.user_id, [])
        if not summaries:
            continue

        quiz_summaries = [s for s in summaries if s.get("quiz_id")]
        reminder_summaries = [s for s in summaries if not s.get("quiz_id")]

        try:
            if quiz_summaries:
                space_names = "、".join(s["space_name"] for s in quiz_summaries[:3])
                total_due = sum(s["due_count"] for s in quiz_summaries)
                # 发送一条汇总通知，附带第一个 quiz 的 ID 供跳转
                await NotificationService.create_and_push(
                    user_id=user_data.user_id,
                    notification_type=NotificationType.REVIEW_QUIZ_READY,
                    title="复习测试已准备好",
                    body=f"「{space_names}」等共 {total_due} 个知识点需要复习，测试题已生成",
                    data={
                        "quiz_id": quiz_summaries[0]["quiz_id"],
                        "action": "start_quiz",
                    },
                )

            if reminder_summaries:
                space_names = "、".join(s["space_name"] for s in reminder_summaries[:3])
                total_due = sum(s["due_count"] for s in reminder_summaries)
                await NotificationService.create_and_push(
                    user_id=user_data.user_id,
                    notification_type=NotificationType.REVIEW_REMINDER,
                    title="复习提醒",
                    body=f"「{space_names}」等共 {total_due} 个知识点到期需要复习",
                    data={"action": "go_review"},
                )
        except Exception:
            logger.warning(
                "Failed to create notification for user=%s",
                user_data.user_id, exc_info=True,
            )


