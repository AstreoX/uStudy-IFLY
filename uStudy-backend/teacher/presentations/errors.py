"""Stable error semantics for live events and historical presentation runs."""

from typing import Any


def normalize_run_error(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    message = str(result.get("message") or result.get("reason") or "PPT Agent 执行失败")
    if "maximum presentation-agent iterations reached" in message:
        result.update(
            error_code="legacy_iteration_limit",
            message="任务因旧版执行轮次限制停止，可继续执行。",
            retryable=False,
            recoverable=True,
        )
    elif result.get("error_code") == "runtime_dependencies" or result.get("reason") == "runtime_dependencies":
        result.update(error_code="runtime_dependencies", message=message, retryable=False, recoverable=False)
    else:
        result.setdefault("error_code", "agent_execution_failed")
        result.setdefault("message", message)
        result.setdefault("recoverable", result.get("retryable") is not False)
    return result
