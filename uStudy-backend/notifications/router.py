"""Notification endpoints.

- SSE stream for real-time push
- REST API for persistent notification CRUD
"""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from auth.dependencies import get_current_user
from db.database import get_db
from db.models import User
from notifications.queue import cleanup_user_queue, get_notification, register_user_queue
from notifications.schemas import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from notifications.service import NotificationService
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["notifications"],
)


# ── SSE Stream (existing) ──


@router.get(
    "/notifications/stream",
    summary="通知 SSE 流",
    description="实时通知推送（掌握分更新等）。前端进入对话页面时建立连接。",
    responses={
        200: {
            "description": "SSE 流式通知",
            "content": {"text/event-stream": {}},
        },
    },
)
async def notification_stream(
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """SSE endpoint for real-time notifications."""

    async def event_generator():
        user_id = current_user.id
        register_user_queue(user_id)
        logger.info("Notification SSE connected: user=%s", user_id)
        try:
            while True:
                notification = await get_notification(user_id, timeout=15.0)
                if notification is None:
                    yield ": heartbeat\n\n"
                else:
                    event_type = notification.get("type", "message")
                    data = notification.get("data", {})
                    yield f"event: {event_type}\n"
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        finally:
            cleanup_user_queue(user_id)
            logger.info("Notification SSE disconnected: user=%s", user_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── REST API (new) ──


@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    summary="获取通知列表",
)
async def get_notifications(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationListResponse:
    items, total = await NotificationService.get_notifications(
        db, current_user.id, offset=offset, limit=limit, unread_only=unread_only,
    )
    unread_count = await NotificationService.get_unread_count(db, current_user.id)

    return NotificationListResponse(
        items=[
            NotificationResponse(
                id=n.id,
                type=n.type.value,
                title=n.title,
                body=n.body,
                data=n.data,
                is_read=n.is_read,
                created_at=n.created_at,
            )
            for n in items
        ],
        total=total,
        unread_count=unread_count,
    )


@router.get(
    "/notifications/unread-count",
    response_model=UnreadCountResponse,
    summary="获取未读通知数量",
)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    count = await NotificationService.get_unread_count(db, current_user.id)
    return UnreadCountResponse(count=count)


@router.patch(
    "/notifications/read-all",
    summary="标记全部通知为已读",
)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = await NotificationService.mark_all_read(db, current_user.id)
    return {"success": True, "marked_count": count}


@router.patch(
    "/notifications/{notification_id}/read",
    summary="标记单条通知为已读",
)
async def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    success = await NotificationService.mark_read(
        db, current_user.id, notification_id,
    )
    return {"success": success}
