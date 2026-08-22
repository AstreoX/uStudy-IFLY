"""Notification service — persist + push in-app notifications."""

import logging
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_scoped_session
from db.models import Notification, NotificationType
from notifications.queue import push_notification

logger = logging.getLogger(__name__)


class NotificationService:
    """通知的创建、查询、标记已读。"""

    @staticmethod
    async def create_and_push(
        user_id: UUID,
        notification_type: NotificationType,
        title: str,
        body: str,
        data: dict | None = None,
    ) -> UUID:
        """持久化通知并通过 SSE 实时推送。

        使用 get_scoped_session() 因为此方法从定时任务等
        非 FastAPI 请求生命周期调用。
        """
        async with get_scoped_session() as session:
            notif = Notification(
                user_id=user_id,
                type=notification_type,
                title=title,
                body=body,
                data=data,
                is_read=False,
            )
            session.add(notif)
            await session.commit()
            await session.refresh(notif)
            notif_id = notif.id

        # 实时推送到 SSE（不阻塞，失败也不影响持久化）
        try:
            await push_notification(user_id, {
                "type": "new_notification",
                "data": {
                    "id": str(notif_id),
                    "type": notification_type.value,
                    "title": title,
                    "body": body,
                    "data": data,
                },
            })
        except Exception:
            logger.warning(
                "Failed to push real-time notification for user=%s", user_id,
                exc_info=True,
            )

        return notif_id

    @staticmethod
    async def get_notifications(
        db: AsyncSession,
        user_id: UUID,
        offset: int = 0,
        limit: int = 20,
        unread_only: bool = False,
    ) -> tuple[list[Notification], int]:
        """分页查询通知列表。"""
        base = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            base = base.where(Notification.is_read == False)  # noqa: E712

        # 总数
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        # 分页列表
        items_stmt = (
            base
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await db.execute(items_stmt)
        items = list(result.scalars().all())

        return items, total

    @staticmethod
    async def get_unread_count(db: AsyncSession, user_id: UUID) -> int:
        """未读通知数量。"""
        stmt = (
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
        )
        return (await db.execute(stmt)).scalar() or 0

    @staticmethod
    async def mark_read(
        db: AsyncSession, user_id: UUID, notification_id: UUID,
    ) -> bool:
        """标记单条通知为已读，返回是否成功。

        调用方通过 get_db() (FastAPI Depends) 管理 session，自动 commit。
        """
        result = await db.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .values(is_read=True)
        )
        return result.rowcount > 0

    @staticmethod
    async def mark_all_read(db: AsyncSession, user_id: UUID) -> int:
        """标记全部通知为已读，返回被标记的数量。

        调用方通过 get_db() (FastAPI Depends) 管理 session，自动 commit。
        """
        result = await db.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read == False,  # noqa: E712
            )
            .values(is_read=True)
        )
        return result.rowcount
