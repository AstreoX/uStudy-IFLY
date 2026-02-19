"""Fire-and-forget study activity recorder."""

import asyncio
import logging
from datetime import date
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.database import get_scoped_session
from db.models import DailyStudyRecord

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task] = set()


async def _record_study_activity(user_id: UUID) -> None:
    """Record a study activity for today (upsert: increment activity_count)."""
    try:
        async with get_scoped_session() as db:
            stmt = pg_insert(DailyStudyRecord).values(
                user_id=user_id,
                study_date=date.today(),
                activity_count=1,
            )
            stmt = stmt.on_conflict_do_update(
                constraint="uq_dsr_user_study_date",
                set_={"activity_count": DailyStudyRecord.activity_count + 1},
            )
            await db.execute(stmt)
            await db.commit()
    except Exception as e:
        logger.error(f"Failed to record study activity for {user_id}: {e}", exc_info=True)


def schedule_study_activity_recording(user_id: UUID) -> None:
    """
    Fire-and-forget: schedule background task to record today's study activity.

    Task references are kept in _background_tasks to prevent GC.
    """
    task = asyncio.create_task(_record_study_activity(user_id))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
