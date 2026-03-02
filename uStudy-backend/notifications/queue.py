"""User notification queue management.

Each user with an active SSE connection gets an asyncio.Queue on the local
worker.  Cross-worker delivery is handled by ``pg_notify`` — this module
only manages the *local* per-user queues.
"""

import asyncio
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

_MAX_QUEUE_SIZE = 100

# Plain dict — queues are created explicitly via register_user_queue()
# so that the LISTEN callback never creates ghost queues on workers
# where the user has no SSE connection.
_user_queues: dict[UUID, asyncio.Queue] = {}


def register_user_queue(user_id: UUID) -> asyncio.Queue:
    """Ensure a queue exists for *user_id* and return it.

    Called by the SSE endpoint when a connection is established.
    Idempotent: returns the existing queue if already present.
    """
    if user_id not in _user_queues:
        _user_queues[user_id] = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
        logger.debug("Registered notification queue for user %s", user_id)
    return _user_queues[user_id]


async def push_notification(user_id: UUID, notification: dict) -> None:
    """Broadcast a notification to *user_id* via PostgreSQL NOTIFY.

    The notification reaches every worker's LISTEN callback; the callback
    enqueues it locally only if the user has an SSE connection on that worker.

    Args:
        user_id: Target user ID
        notification: Dict with 'type' and 'data' keys
    """
    from notifications.pg_notify import notify

    await notify(user_id, notification)


async def get_notification(user_id: UUID, timeout: float = 30.0) -> dict | None:
    """Get the next notification from the user's local queue.

    Returns None on timeout (used for SSE heartbeat).

    Args:
        user_id: User ID
        timeout: Max seconds to wait

    Returns:
        Notification dict or None on timeout
    """
    queue = _user_queues.get(user_id)
    if queue is None:
        await asyncio.sleep(timeout)
        return None
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
