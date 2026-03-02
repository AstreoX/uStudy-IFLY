"""认证审计日志"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import logging

try:
    import structlog
except ImportError:  # pragma: no cover - optional dependency
    structlog = None

if structlog:
    logger = structlog.get_logger()
else:
    logger = logging.getLogger("auth")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def log_auth_event(
    event_type: str,
    email: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    success: bool = True,
    details: dict[str, Any] | None = None,
) -> None:
    """记录认证相关事件"""
    if structlog:
        log_method = logger.info if success else logger.warning
        log_method(
            "auth_event",
            event_type=event_type,
            email=email,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            details=details or {},
            timestamp=_now_iso(),
        )
        return

    level = logging.INFO if success else logging.WARNING
    logger.log(
        level,
        "auth_event",
        extra={
            "event_type": event_type,
            "email": email,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "details": details or {},
            "timestamp": _now_iso(),
        },
    )
