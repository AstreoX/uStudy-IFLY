"""登录安全机制"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from auth.exceptions import AccountLockedError

LOGIN_FAIL_LIMIT = 5
LOCKOUT_MINUTES = 15

_login_failures: dict[str, list[datetime]] = defaultdict(list)
_lock = asyncio.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def check_login_allowed(email: str) -> None:
    """检查账户是否被锁定"""
    async with _lock:
        failures = _login_failures.get(email, [])
        cutoff = _now() - timedelta(minutes=LOCKOUT_MINUTES)
        failures = [f for f in failures if f > cutoff]
        _login_failures[email] = failures

        if len(failures) >= LOGIN_FAIL_LIMIT:
            oldest_in_window = min(failures)
            remaining = LOCKOUT_MINUTES - int(
                (_now() - oldest_in_window).total_seconds() / 60
            )
            remaining = max(1, remaining)
            raise AccountLockedError(
                f"登录失败次数过多，请 {remaining} 分钟后重试"
            )


async def record_login_failure(email: str) -> None:
    """记录登录失败"""
    async with _lock:
        _login_failures[email].append(_now())


async def clear_login_failures(email: str) -> None:
    """登录成功后清除失败记录"""
    async with _lock:
        _login_failures.pop(email, None)
