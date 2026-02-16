"""Notification SSE endpoint.

Provides a persistent SSE connection per user for real-time notifications
(mastery updates, etc.). The frontend establishes this connection when
entering the spaceChat page.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from auth.dependencies import get_current_user
from db.models import User
from notifications.queue import get_notification, cleanup_user_queue

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["notifications"],
)


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
