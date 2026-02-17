"""Cross-worker notification broadcast via PostgreSQL LISTEN/NOTIFY.

Each uvicorn worker starts a dedicated raw asyncpg connection that LISTENs
on a shared channel.  When any worker calls ``notify()``, PostgreSQL
broadcasts the payload to every listener; the callback then checks whether
the target user has an SSE connection on *this* worker and, if so, enqueues
the notification locally.

Connection details
------------------
- LISTEN uses a raw ``asyncpg.connect()`` (must be persistent, cannot be
  pooled).
- NOTIFY reuses the existing SQLAlchemy async engine (``text(SELECT
  pg_notify(...))``), so no extra connections are needed.
"""

import asyncio
import json
import logging
from uuid import UUID

import asyncpg
from sqlalchemy import text

from config import get_settings
from db.database import engine

logger = logging.getLogger(__name__)

CHANNEL = "user_notifications"
_MAX_PAYLOAD_BYTES = 7500  # PG hard limit is 8000; leave headroom

_listener_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


# ---------------------------------------------------------------------------
# NOTIFY — called from any worker to broadcast a notification
# ---------------------------------------------------------------------------

async def notify(user_id: UUID, notification: dict) -> None:
    """Send a NOTIFY on the shared PG channel.

    Serialises *notification* together with *user_id* into a JSON payload
    and executes ``SELECT pg_notify(...)`` via the SQLAlchemy pool.
    """
    payload = json.dumps(
        {"user_id": str(user_id), "notification": notification},
        ensure_ascii=False,
    )

    payload_size = len(payload.encode())
    if payload_size > _MAX_PAYLOAD_BYTES:
        logger.warning(
            "NOTIFY payload too large (%d bytes) for user %s — dropped",
            payload_size,
            user_id,
        )
        return

    try:
        async with engine.connect() as conn:
            await conn.execute(
                text("SELECT pg_notify(:channel, :payload)"),
                {"channel": CHANNEL, "payload": payload},
            )
            await conn.commit()
        logger.debug("Sent NOTIFY for user %s", user_id)
    except Exception:
        logger.exception("Failed to send NOTIFY for user %s", user_id)


# ---------------------------------------------------------------------------
# LISTEN — one long-lived connection per worker
# ---------------------------------------------------------------------------

def _on_notification(
    conn: asyncpg.Connection,
    pid: int,
    channel: str,
    payload: str,
) -> None:
    """asyncpg listener callback — runs in the event-loop thread."""
    from notifications.queue import _user_queues

    try:
        data = json.loads(payload)
        user_id = UUID(data["user_id"])
        notification = data["notification"]
    except (json.JSONDecodeError, KeyError, ValueError):
        logger.warning("Malformed NOTIFY payload: %s", payload[:200])
        return

    queue = _user_queues.get(user_id)
    if queue is None:
        return  # user not connected on this worker

    try:
        queue.put_nowait(notification)
        logger.debug(
            "Delivered cross-worker notification to user %s", user_id
        )
    except asyncio.QueueFull:
        logger.warning(
            "Queue full for user %s — cross-worker notification dropped",
            user_id,
        )


async def _listen_loop(stop: asyncio.Event) -> None:
    """Maintain a persistent LISTEN connection with auto-reconnect."""
    settings = get_settings()
    raw_url = settings.database_url
    prefix = "postgresql+asyncpg://"
    if raw_url.startswith(prefix):
        dsn = "postgresql://" + raw_url[len(prefix):]
    else:
        dsn = raw_url

    backoff = 1.0
    max_backoff = 30.0

    while not stop.is_set():
        conn: asyncpg.Connection | None = None
        try:
            conn = await asyncpg.connect(dsn)
            await conn.add_listener(CHANNEL, _on_notification)
            logger.info("PG LISTEN connected on channel '%s'", CHANNEL)
            backoff = 1.0  # reset on successful connect

            # Health-check loop: SELECT 1 every 30 s
            while not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=30.0)
                    break  # stop requested
                except asyncio.TimeoutError:
                    await conn.execute("SELECT 1")

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception(
                "LISTEN connection error — reconnecting in %.0fs", backoff
            )
            try:
                await asyncio.wait_for(stop.wait(), timeout=backoff)
                break  # stop requested during backoff
            except asyncio.TimeoutError:
                pass
            backoff = min(backoff * 2, max_backoff)
        finally:
            if conn is not None:
                try:
                    await conn.remove_listener(CHANNEL, _on_notification)
                    await conn.close()
                except Exception:
                    pass

    logger.info("PG LISTEN loop stopped")


async def start_listener() -> None:
    """Start the background LISTEN task (called during app lifespan)."""
    global _listener_task, _stop_event
    _stop_event = asyncio.Event()
    _listener_task = asyncio.create_task(_listen_loop(_stop_event))
    logger.info("PG LISTEN task started")


async def stop_listener() -> None:
    """Gracefully stop the background LISTEN task."""
    global _listener_task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _listener_task is not None:
        try:
            await asyncio.wait_for(_listener_task, timeout=5.0)
        except asyncio.TimeoutError:
            _listener_task.cancel()
            try:
                await _listener_task
            except asyncio.CancelledError:
                pass
    _listener_task = None
    _stop_event = None
    logger.info("PG LISTEN task stopped")
