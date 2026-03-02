"""学习活动服务 — 测验活动记录（无需 LLM）"""

import logging
from datetime import date, datetime, timezone
from uuid import UUID

from db.database import get_scoped_session
from db.models import StudyActivityLog

logger = logging.getLogger(__name__)


async def record_quiz_activity(
    user_id: UUID,
    quiz_topic: str,
    quiz_space_id: UUID | None,
    quiz_space_name: str | None,
    score: int,
    total_score: int,
) -> None:
    """
    记录测验完成活动（fire-and-forget，无需 LLM）。

    Args:
        user_id: 用户 ID
        quiz_topic: 测验主题
        quiz_space_id: 学习空间 ID
        quiz_space_name: 学习空间名称
        score: 用户得分
        total_score: 总分
    """
    try:
        now = datetime.now(timezone.utc)
        async with get_scoped_session() as session:
            activity = StudyActivityLog(
                user_id=user_id,
                conversation_id=None,
                space_id=quiz_space_id,
                title=f"{quiz_topic} 测验",
                summary=f"完成测验，得分 {score}/{total_score}",
                activity_type="测验",
                subject_name=quiz_space_name[:200] if quiz_space_name else None,
                related_node_labels=None,
                message_count=0,
                study_depth=None,
                source="quiz",
                activity_date=now.date(),
                activity_time=now,
            )
            session.add(activity)
            await session.commit()
            logger.info(f"Recorded quiz activity for user {user_id}: {quiz_topic}")
    except Exception as e:
        logger.error(
            f"Failed to record quiz activity for user {user_id}: {e}",
            exc_info=True,
        )
