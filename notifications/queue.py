"""In-memory notification queue management.

Each user gets an independent asyncio.Queue for real-time notification delivery.
Notifications are consumed by the SSE endpoint in notifications/router.py.
"""

import asyncio
import logging
from collections import defaultdict
from uuid import UUID

logger = logging.getLogger(__name__)

_MAX_QUEUE_SIZE = 100

_user_queues: dict[UUID, asyncio.Queue] = defaultdict(
    lambda: asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
)


async def push_notification(user_id: UUID, notification: dict) -> None:
    """Push a notification to the user's queue.

    Drops the notification silently if the queue is full (user not connected
    or consuming too slowly).

    Args:
        user_id: Target user ID
        notification: Dict with 'type' and 'data' keys
    """
    queue = _user_queues[user_id]
    try:
        queue.put_nowait(notification)
        logger.debug("Pushed notification to user %s: type=%s", user_id, notification.get("type"))
    except asyncio.QueueFull:
        logger.warning("Notification queue full for user %s, dropping notification", user_id)


async def get_notification(user_id: UUID, timeout: float = 30.0) -> dict | None:
    """Get the next notification from the user's queue.

    Returns None on timeout (used for SSE heartbeat).

    Args:
        user_id: User ID
        timeout: Max seconds to wait

    Returns:
        Notification dict or None on timeout
    """
    queue = _user_queues[user_id]
    try:
        return await asyncio.wait_for(queue.get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


def cleanup_user_queue(user_id: UUID) -> None:
    """Remove the user's queue when they disconnect.

    Args:
        user_id: User ID to clean up
    """
    if user_id in _user_queues:
        del _user_queues[user_id]
        logger.debug("Cleaned up notification queue for user %s", user_id)
