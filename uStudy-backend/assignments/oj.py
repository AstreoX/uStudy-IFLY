"""Authenticated control-plane client for the isolated OJ manager.

The manager owns all hidden tests. This module deliberately exposes only a
small allowlisted result shape to the uStudy API and never executes code.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from config import get_settings

TERMINAL_STATUSES = {"completed", "failed"}
ALLOWED_VERDICTS = {
    "accepted", "wrong_answer", "compile_error", "runtime_error",
    "time_limit_exceeded", "memory_limit_exceeded", "output_limit_exceeded",
    "dangerous_syscall", "system_error",
}


class OjManagerError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool, status_code: int = 503):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status_code = status_code


class OjClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.oj_enabled:
            raise OjManagerError("OJ_DISABLED", "OJ 功能尚未启用", retryable=False, status_code=503)
        token = settings.oj_manager_token_resolved
        if not token:
            raise OjManagerError("OJ_MISCONFIGURED", "OJ 服务未配置", retryable=False, status_code=503)
        self.base_url = settings.oj_manager_url.rstrip("/") + "/api/v1"
        self.headers = {"Authorization": f"Bearer {token}"}
        self.timeout = settings.oj_request_timeout_seconds

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, headers=self.headers, timeout=self.timeout
            ) as client:
                response = await client.request(method, path, **kwargs)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise OjManagerError("OJ_UNAVAILABLE", "OJ 服务暂时不可用", retryable=True) from exc
        if response.status_code == 429:
            raise OjManagerError("OJ_QUEUE_FULL", "OJ 判题队列已满，请稍后重试", retryable=False, status_code=429)
        if response.status_code >= 500:
            raise OjManagerError("OJ_UNAVAILABLE", "OJ 服务暂时不可用", retryable=True) from None
        if response.status_code in {401, 403}:
            raise OjManagerError("OJ_AUTH_FAILED", "OJ 服务认证失败", retryable=False, status_code=503)
        if response.status_code == 404:
            raise OjManagerError("OJ_RESOURCE_NOT_FOUND", "OJ 资源不存在", retryable=False, status_code=404)
        if response.status_code == 409:
            raise OjManagerError("OJ_CONFLICT", "OJ 请求与现有任务冲突", retryable=False, status_code=409)
        if response.status_code >= 400:
            message = "OJ 请求无效"
            try:
                detail = response.json().get("detail")
                message = detail if isinstance(detail, str) else message
            except (ValueError, AttributeError):
                pass
            raise OjManagerError("OJ_INVALID_REQUEST", message, retryable=False, status_code=422)
        try:
            payload = response.json()
        except ValueError as exc:
            raise OjManagerError("OJ_PROTOCOL_ERROR", "OJ 服务响应无效", retryable=True) from exc
        if not isinstance(payload, dict):
            raise OjManagerError("OJ_PROTOCOL_ERROR", "OJ 服务响应无效", retryable=True)
        return payload

    async def create_draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/problems/drafts", json=payload)

    async def get_draft(self, draft_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/problems/drafts/{draft_id}")

    async def update_draft(self, draft_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PUT", f"/problems/drafts/{draft_id}", json=payload)

    async def import_draft(self, draft_id: str, filename: str, content: bytes) -> dict[str, Any]:
        return await self._request(
            "POST", f"/problems/drafts/{draft_id}/import",
            files={"file": (filename, content, "application/zip")},
        )

    async def validate_draft(self, draft_id: str, idempotency_key: str) -> dict[str, Any]:
        return await self._request(
            "POST", f"/problems/drafts/{draft_id}/validate",
            json={"idempotency_key": idempotency_key},
        )

    async def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/runs", json=payload)

    async def get_run(self, run_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/runs/{run_id}")

    async def wait_run(self, run_id: str) -> dict[str, Any]:
        settings = get_settings()
        loop = asyncio.get_running_loop()
        deadline = loop.time() + settings.oj_run_timeout_seconds
        while True:
            result = await self.get_run(run_id)
            if result.get("status") in TERMINAL_STATUSES:
                return result
            if loop.time() >= deadline:
                raise OjManagerError("OJ_TIMEOUT", "OJ 判题超时", retryable=True)
            await asyncio.sleep(settings.oj_run_poll_seconds)


def sanitize_run_result(payload: dict[str, Any], *, include_samples: bool) -> dict[str, Any]:
    """Allowlist public fields and normalize manager `group_results` to `groups`."""
    verdict = payload.get("verdict")
    if verdict not in ALLOWED_VERDICTS:
        verdict = "system_error" if payload.get("status") == "failed" else None
    result: dict[str, Any] = {
        "status": str(payload.get("status") or "pending"),
        "verdict": verdict,
        "score": payload.get("score"),
        "groups": [],
        "compile_output": str(payload.get("compile_output"))[:65536]
        if payload.get("compile_output") is not None else None,
        "time_ms": payload.get("time_ms"),
        "memory_kb": payload.get("memory_kb"),
    }
    for group in payload.get("group_results") or []:
        if isinstance(group, dict):
            result["groups"].append({
                key: group.get(key)
                for key in ("name", "verdict", "score", "max_score", "time_ms", "memory_kb")
                if key in group
            })
    if include_samples:
        result["samples"] = []
        for sample in payload.get("samples") or []:
            if isinstance(sample, dict):
                result["samples"].append({
                    key: sample.get(key)
                    for key in (
                        "input", "expected_output", "stdout", "actual_output", "stderr",
                        "verdict", "time_ms", "memory_kb",
                    )
                    if key in sample
                })
    return result
