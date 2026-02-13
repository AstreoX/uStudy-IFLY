"""Daily usage report scheduled job."""

import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_scoped_session
from db.models import User
from scheduler.email.usage_report_service import UsageReportEmailService
from scheduler.models import SchedulerState
from usage.models import ApiUsageLog

logger = logging.getLogger(__name__)

JOB_ID = "daily_usage_report"
BEIJING_TZ = ZoneInfo("Asia/Shanghai")


async def send_daily_usage_report() -> None:
    """
    Send daily usage report email.

    This job runs at 20:30 Beijing time daily.
    Reports on the previous calendar day's usage (UTC).

    Uses a 3-phase pattern to minimize lock holding time:
    1. Check if already run (no lock)
    2. Gather data and send email (no lock, no DB during send)
    3. Update state with brief lock

    Handles multi-worker deduplication via database row locking.
    """
    logger.info("Starting daily usage report job")

    # Use Beijing time for deduplication (consistent with scheduler timezone)
    today_beijing = datetime.now(BEIJING_TZ).date()
    # Report covers yesterday UTC (at 20:30 Beijing = 12:30 UTC, dates match)
    yesterday_utc = datetime.now(timezone.utc).date() - timedelta(days=1)

    try:
        # Phase 1: Quick check if already run today (no lock needed)
        row_exists = False
        async with get_scoped_session() as db:
            check_result = await db.execute(
                select(SchedulerState.last_run_date).where(
                    SchedulerState.job_id == JOB_ID
                )
            )
            existing_date = check_result.scalar_one_or_none()

            if existing_date is not None:
                row_exists = True
                if existing_date == today_beijing:
                    logger.info(
                        "Daily report already sent today (%s), skipping", today_beijing
                    )
                    return

        # Phase 2: Gather report data (read-only, no lock needed)
        async with get_scoped_session() as db:
            report_data = await _gather_report_data(db, yesterday_utc)

        # Phase 3a: Send email (no DB session held during network I/O)
        email_service = UsageReportEmailService()
        success = await email_service.send_daily_report(
            report_date=yesterday_utc,
            report_data=report_data,
        )

        if not success:
            logger.error("Failed to send daily usage report for %s", yesterday_utc)
            return

        logger.info("Daily usage report sent successfully for %s", yesterday_utc)

        # Phase 3b: Update state with brief lock
        async with get_scoped_session() as db:
            if row_exists:
                # Try to acquire lock and update
                lock_result = await db.execute(
                    select(SchedulerState)
                    .where(SchedulerState.job_id == JOB_ID)
                    .with_for_update(skip_locked=True)
                )
                state = lock_result.scalar_one_or_none()

                if state is None:
                    # Another worker has the lock, they will update
                    logger.info("Another worker is updating state, skipping")
                    return

                # Double-check after acquiring lock
                if state.last_run_date == today_beijing:
                    logger.info(
                        "State already updated by another worker, skipping commit"
                    )
                    return

                await db.execute(
                    update(SchedulerState)
                    .where(SchedulerState.job_id == JOB_ID)
                    .values(last_run_date=today_beijing, last_run_at=func.now())
                )
            else:
                # First run - insert new row, handle race with IntegrityError
                db.add(
                    SchedulerState(
                        job_id=JOB_ID,
                        last_run_date=today_beijing,
                    )
                )

            try:
                await db.commit()
            except IntegrityError:
                # Another worker inserted first - that's fine, they recorded it
                logger.info("Another worker already inserted state record")
                await db.rollback()

    except Exception:
        logger.exception("Error in daily usage report job")


async def _gather_report_data(db: AsyncSession, report_date: date) -> dict:
    """
    Gather comprehensive usage data for the report.

    Args:
        db: Database session
        report_date: The date to report on (typically yesterday UTC)

    Returns:
        Dictionary containing all report data
    """
    start_dt = datetime.combine(report_date, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)

    # Total users count
    total_users_result = await db.execute(select(func.count(User.id)))
    total_users = total_users_result.scalar() or 0

    # Active users (users who made API calls on report date)
    active_users_result = await db.execute(
        select(func.count(func.distinct(ApiUsageLog.user_id)))
        .where(ApiUsageLog.created_at >= start_dt)
        .where(ApiUsageLog.created_at < end_dt)
    )
    active_users = active_users_result.scalar() or 0

    # Aggregate stats
    agg_result = await db.execute(
        select(
            func.coalesce(func.sum(ApiUsageLog.total_tokens), 0).label("total_tokens"),
            func.count().label("total_calls"),
            func.coalesce(func.sum(ApiUsageLog.estimated_cost_cents), 0).label("cost"),
        )
        .where(ApiUsageLog.created_at >= start_dt)
        .where(ApiUsageLog.created_at < end_dt)
    )
    agg = agg_result.one()

    # By usage type
    type_result = await db.execute(
        select(
            ApiUsageLog.usage_type,
            func.coalesce(func.sum(ApiUsageLog.total_tokens), 0).label("tokens"),
            func.count().label("calls"),
            func.coalesce(func.sum(ApiUsageLog.estimated_cost_cents), 0).label("cost"),
        )
        .where(ApiUsageLog.created_at >= start_dt)
        .where(ApiUsageLog.created_at < end_dt)
        .group_by(ApiUsageLog.usage_type)
    )
    by_type = [
        {
            "usage_type": row.usage_type.value,
            "tokens": row.tokens,
            "calls": row.calls,
            "cost_cents": row.cost,
        }
        for row in type_result
    ]

    # By model
    model_result = await db.execute(
        select(
            ApiUsageLog.model,
            func.coalesce(func.sum(ApiUsageLog.total_tokens), 0).label("tokens"),
            func.count().label("calls"),
            func.coalesce(func.sum(ApiUsageLog.estimated_cost_cents), 0).label("cost"),
        )
        .where(ApiUsageLog.created_at >= start_dt)
        .where(ApiUsageLog.created_at < end_dt)
        .group_by(ApiUsageLog.model)
        .order_by(func.sum(ApiUsageLog.total_tokens).desc())
    )
    by_model = [
        {
            "model": row.model,
            "tokens": row.tokens,
            "calls": row.calls,
            "cost_cents": row.cost,
        }
        for row in model_result
    ]

    # Top 10 users by token usage
    top_users_result = await db.execute(
        select(
            User.email,
            User.nickname,
            func.coalesce(func.sum(ApiUsageLog.total_tokens), 0).label("tokens"),
            func.count().label("calls"),
        )
        .join(User, ApiUsageLog.user_id == User.id)
        .where(ApiUsageLog.created_at >= start_dt)
        .where(ApiUsageLog.created_at < end_dt)
        .group_by(User.id, User.email, User.nickname)
        .order_by(func.sum(ApiUsageLog.total_tokens).desc())
        .limit(10)
    )
    top_users = [
        {
            "email": row.email,
            "nickname": row.nickname,
            "tokens": row.tokens,
            "calls": row.calls,
        }
        for row in top_users_result
    ]

    return {
        "report_date": report_date,
        "total_users": total_users,
        "active_users": active_users,
        "total_tokens": agg.total_tokens,
        "total_calls": agg.total_calls,
        "estimated_cost_cents": agg.cost,
        "by_usage_type": by_type,
        "by_model": by_model,
        "top_users": top_users,
    }
