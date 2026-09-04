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

    settings = get_settings()

    # Only register scheduler jobs in non-test environments
    if settings.app_env == "test":
        logger.info("Test environment detected, skipping job registration")
        return

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

    async def _recover_assignment_jobs():
        from assignments.tasks import recover_assignment_jobs

        try:
            await recover_assignment_jobs()
        except Exception as e:
            logger.error("Failed to recover assignment jobs: %s", e, exc_info=True)

    sched.add_job(
        _recover_assignment_jobs,
        trigger=IntervalTrigger(seconds=30),
        id="recover_assignment_jobs",
        name="Recover durable assignment generation/grading jobs",
        replace_existing=True,
    )
    logger.info("Registered recover_assignment_jobs job (every 30 sec)")

    # Daily review quiz generation and in-app notifications at 08:00 Beijing time.
    # Only spaces whose owners manually enable review_mode > 0 are processed.
    from scheduler.jobs.daily_review_processor import process_daily_reviews

    sched.add_job(
        process_daily_reviews,
        trigger=CronTrigger(
            hour=8,
            minute=0,
            timezone="Asia/Shanghai",
        ),
        id="daily_review_processor",
        name="Daily Review Quiz Generation & In-App Notifications",
        replace_existing=True,
    )
    logger.info("Registered daily_review_processor job for 08:00 Asia/Shanghai")


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
