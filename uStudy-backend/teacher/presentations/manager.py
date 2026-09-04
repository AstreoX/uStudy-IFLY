"""HTTP client for the separately deployed Presentation Sandbox Manager."""

from __future__ import annotations

import os
from typing import Any

import httpx

from config import get_settings


class SandboxManagerError(RuntimeError):
    pass


class SandboxManagerClient:
    def __init__(self, base_url: str | None = None, timeout: float = 20.0) -> None:
        settings = get_settings()
        configured = getattr(settings, "presentation_sandbox_manager_url", None)
        self.base_url = (
            base_url
            or configured
            or os.getenv("PRESENTATION_SANDBOX_MANAGER_URL", "http://presentation-sandbox-manager:8090")
        ).rstrip("/")
        self.token = (
            getattr(settings, "presentation_sandbox_manager_token", None)
            or os.getenv("PRESENTATION_SANDBOX_MANAGER_TOKEN", "")
        )
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise SandboxManagerError("PRESENTATION_SANDBOX_MANAGER_TOKEN 未配置")
        return {"Authorization": f"Bearer {self.token}"}

    async def create_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/runs", json=payload, headers=self._headers()
            )
        if response.is_error:
            raise SandboxManagerError(
                f"sandbox manager create failed ({response.status_code}): {response.text[:500]}"
            )
        data = response.json()
        if not (data.get("run_id") or data.get("id")):
            raise SandboxManagerError("sandbox manager response missing run id")
        return data

    async def cancel_run(self, manager_run_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/runs/{manager_run_id}/cancel", headers=self._headers()
            )
        if response.is_error:
            raise SandboxManagerError(
                f"sandbox manager cancel failed ({response.status_code}): {response.text[:500]}"
            )
        return response.json() if response.content else {"status": "cancelled"}

    async def resume_run(self, manager_run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/runs/{manager_run_id}/resume",
                json=payload,
                headers=self._headers(),
            )
        if response.is_error:
            raise SandboxManagerError(
                f"sandbox manager resume failed ({response.status_code}): {response.text[:500]}"
            )
        return response.json()

    async def get_run(self, manager_run_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/runs/{manager_run_id}", headers=self._headers()
            )
        if response.is_error:
            raise SandboxManagerError(
                f"sandbox manager status failed ({response.status_code}): {response.text[:500]}"
            )
        return response.json()
