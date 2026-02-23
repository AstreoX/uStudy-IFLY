"""Scheduler core initialization and lifecycle management."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import get_settings

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler: AsyncIOScheduler | None = None


def _create_scheduler() -> AsyncIOScheduler:
    """Create and configure the scheduler."""
    return AsyncIOScheduler(
        timezone="Asia/Shanghai",  # Beijing time (UTC+8)
        job_defaults={
            "coalesce": True,  # Combine missed runs into one
            "max_instances": 1,  # Only one instance of each job at a time
            "misfire_grace_time": 3600,  # 1 hour grace time for missed jobs
        },
    )


def _register_jobs(sched: AsyncIOScheduler) -> None:
    """Register all scheduled jobs."""
    from apscheduler.triggers.interval import IntervalTrigger

    from scheduler.jobs.daily_usage_report import send_daily_usage_report

    settings = get_settings()

    # Only register scheduler jobs in non-test environments
    if settings.app_env == "test":
        logger.info("Test environment detected, skipping job registration")
        return

    # Daily usage report at 20:30 Beijing time
    sched.add_job(
        send_daily_usage_report,
        trigger=CronTrigger(
            hour=20,
            minute=30,
            timezone="Asia/Shanghai",
        ),
        id="daily_usage_report",
        name="Daily Usage Report Email",
        replace_existing=True,
    )
    logger.info("Registered daily_usage_report job for 20:30 Asia/Shanghai")

    # Cleanup expired client tool requests every 5 minutes
    async def _cleanup_expired_tool_requests():
        from chat.tools.client_tool_bridge import cleanup_expired_requests

        try:
            await cleanup_expired_requests(max_age_seconds=300)
        except Exception as e:
            logger.error(f"Failed to cleanup expired tool requests: {e}")

    sched.add_job(
        _cleanup_expired_tool_requests,
        trigger=IntervalTrigger(minutes=5),
        id="cleanup_expired_tool_requests",
        name="Cleanup Expired Client Tool Requests",
        replace_existing=True,
    )
    logger.info("Registered cleanup_expired_tool_requests job (every 5 min)")

    # Expire stale payment orders every 5 minutes
    async def _expire_stale_payment_orders():
        from payment.service import expire_stale_orders

        try:
            await expire_stale_orders()
        except Exception as e:
            logger.error(f"Failed to expire stale payment orders: {e}")

    sched.add_job(
        _expire_stale_payment_orders,
        trigger=IntervalTrigger(minutes=5),
        id="expire_stale_payment_orders",
        name="Expire Stale Payment Orders",
        replace_existing=True,
    )
    logger.info("Registered expire_stale_payment_orders job (every 5 min)")


@asynccontextmanager
async def get_scheduler_lifespan() -> AsyncGenerator[None, None]:
    """
    Scheduler lifespan context manager for FastAPI integration.

    Usage in main.py:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with get_scheduler_lifespan():
                yield

        app = FastAPI(lifespan=lifespan)
    """
    global scheduler

    scheduler = _create_scheduler()
    _register_jobs(scheduler)

    scheduler.start()
    logger.info("Scheduler started")

    try:
        yield
    finally:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler shut down")
