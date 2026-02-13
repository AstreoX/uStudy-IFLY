"""Client Tool Bridge — manages pending client-side tool requests.

Workflow:
1. Orchestrator creates a pending request (DB + in-memory Event).
2. SSE emits client_tool_request event to the frontend.
3. Frontend executes the tool (e.g. Android calendar) and POSTs result.
4. Router calls submit_tool_result → writes DB + sets Event.
5. Orchestrator's wait_for_result returns the ToolResult.

Cross-worker strategy:
- asyncio.Event works when SSE stream and POST hit the same worker (common case).
- DB polling (500 ms) serves as fallback for cross-worker scenarios.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update

from chat.tools.base import ToolResult
from db.database import get_scoped_session
from db.models import PendingClientToolRequest

logger = logging.getLogger(__name__)

# In-memory registry: tool_call_id → asyncio.Event
# Only effective within the same worker process.
_pending_events: dict[str, asyncio.Event] = {}


async def create_pending_request(
    conversation_id: UUID,
    tool_call_id: str,
    tool_name: str,
    params: dict[str, Any],
) -> None:
    """Write a pending request row to DB and register an in-memory Event."""
    # Register in-memory event BEFORE DB commit to avoid race condition:
    # a fast POST could arrive between commit and event registration.
    event = asyncio.Event()
    _pending_events[tool_call_id] = event

    try:
        async with get_scoped_session() as db:
            row = PendingClientToolRequest(
                id=uuid4(),
                conversation_id=conversation_id,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                params=params,
                status="pending",
            )
            db.add(row)
            await db.commit()
    except Exception:
        _pending_events.pop(tool_call_id, None)
        raise

    logger.info("Created pending client tool request: %s (%s)", tool_call_id, tool_name)


async def submit_tool_result(
    tool_call_id: str,
    success: bool,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    conversation_id: UUID | None = None,
) -> bool:
    """Write the client's result to DB and signal the in-memory Event.

    Args:
        conversation_id: If provided, verifies the tool_call_id belongs to this
            conversation (defense in depth).

    Returns True if the request was found and updated, False otherwise.
    """
    now = datetime.now(timezone.utc)

    async with get_scoped_session() as db:
        conditions = [
            PendingClientToolRequest.tool_call_id == tool_call_id,
            PendingClientToolRequest.status == "pending",
        ]
        if conversation_id is not None:
            conditions.append(
                PendingClientToolRequest.conversation_id == conversation_id
            )
        stmt = (
            update(PendingClientToolRequest)
            .where(*conditions)
            .values(
                status="completed",
                result_data={"success": success, "result": result, "error": error},
                error_message=error,
                completed_at=now,
            )
        )
        res = await db.execute(stmt)
        await db.commit()

        if res.rowcount == 0:
            logger.warning("submit_tool_result: no pending request for %s", tool_call_id)
            return False

    # Signal in-memory event (same-worker fast path)
    event = _pending_events.pop(tool_call_id, None)
    if event is not None:
        event.set()

    logger.info("Submitted tool result for %s, success=%s", tool_call_id, success)
    return True


async def wait_for_result(
    tool_call_id: str,
    timeout: float = 60.0,
    poll_interval: float = 0.5,
) -> ToolResult:
    """Wait for the client to submit the tool result.

    Strategy:
    1. Wait on the in-memory asyncio.Event (fast, same-worker).
    2. If Event doesn't fire within timeout, fall back to DB polling.
    3. If nothing arrives by timeout, return a timeout error ToolResult.
    """
    event = _pending_events.get(tool_call_id)

    if event is not None:
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass  # Fall through to DB check
        finally:
            _pending_events.pop(tool_call_id, None)

        # Check DB for result (Event may have been set)
        row = await _fetch_completed_row(tool_call_id)
        if row is not None:
            return _row_to_tool_result(row)
    else:
        # Cross-worker: no local event, poll DB
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            row = await _fetch_completed_row(tool_call_id)
            if row is not None:
                return _row_to_tool_result(row)
            await asyncio.sleep(poll_interval)

    # Timeout — mark row as timeout in DB
    await _mark_timeout(tool_call_id)
    logger.warning("Client tool request timed out: %s", tool_call_id)
    return ToolResult(
        success=False,
        data=None,
        message="客户端工具请求超时，未收到前端回传结果",
    )


async def cleanup_expired_requests(max_age_seconds: int = 300) -> int:
    """Delete pending requests older than max_age_seconds. Returns count deleted.

    Also purges stale in-memory events that may have been orphaned.
    """
    from datetime import timedelta

    from sqlalchemy import delete as sa_delete

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)

    # Fetch tool_call_ids that will be deleted, so we can clean up _pending_events
    async with get_scoped_session() as db:
        expired_rows = await db.execute(
            select(PendingClientToolRequest.tool_call_id).where(
                PendingClientToolRequest.created_at < cutoff,
            )
        )
        expired_ids = [row[0] for row in expired_rows.all()]

    # Purge matching in-memory events
    for tool_call_id in expired_ids:
        _pending_events.pop(tool_call_id, None)

    # Delete expired rows
    async with get_scoped_session() as db:
        stmt = sa_delete(PendingClientToolRequest).where(
            PendingClientToolRequest.created_at < cutoff,
        )
        res = await db.execute(stmt)
        await db.commit()
        count = res.rowcount
        if count > 0:
            logger.info("Cleaned up %d expired client tool requests", count)
        return count


# ---- internal helpers ----


async def _fetch_completed_row(
    tool_call_id: str,
) -> PendingClientToolRequest | None:
    async with get_scoped_session() as db:
        result = await db.execute(
            select(PendingClientToolRequest).where(
                PendingClientToolRequest.tool_call_id == tool_call_id,
                PendingClientToolRequest.status == "completed",
            )
        )
        return result.scalar_one_or_none()


def _row_to_tool_result(row: PendingClientToolRequest) -> ToolResult:
    data = row.result_data or {}
    if data.get("success", False):
        return ToolResult(
            success=True,
            data=data.get("result"),
            message="操作成功",
        )
    return ToolResult(
        success=False,
        data=data.get("result"),
        message=data.get("error") or "客户端工具执行失败",
    )


async def _mark_timeout(tool_call_id: str) -> None:
    async with get_scoped_session() as db:
        stmt = (
            update(PendingClientToolRequest)
            .where(
                PendingClientToolRequest.tool_call_id == tool_call_id,
                PendingClientToolRequest.status == "pending",
            )
            .values(status="timeout")
        )
        await db.execute(stmt)
        await db.commit()
