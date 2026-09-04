"""HTTP client for the backend's project-scoped capability gateway."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, Self
from urllib.parse import quote

import httpx

from presentation_agent.models import AgentScope


class CapabilityGateway:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        scope: AgentScope,
        timeout_seconds: float = 600,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.scope = scope
        # The backend persists its queued event at sequence 1.
        self._event_sequence = 1
        self._event_lock = asyncio.Lock()
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Presentation-Run": scope.run_id,
                "X-Presentation-Project": scope.project_id,
            },
            timeout=httpx.Timeout(
                connect=10, read=timeout_seconds, write=60, pool=30
            ),
            transport=transport,
        )

    def _scope_payload(self) -> dict[str, str]:
        return self.scope.model_dump()

    @property
    def event_sequence(self) -> int:
        return self._event_sequence

    async def sync_state(self) -> dict[str, Any]:
        """Continue event numbering from the host after a container restart."""

        response = await self._client.get("state")
        response.raise_for_status()
        payload = response.json()
        self._event_sequence = max(
            self._event_sequence, int(payload.get("last_sequence") or 0)
        )
        return payload

    async def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        response = await self._client.post(
            "llm", json={"messages": messages, "tools": tools, "scope": self._scope_payload()}
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload.get("message"), dict):
            return payload["message"]
        choices = payload.get("choices") or []
        if choices and isinstance(choices[0].get("message"), dict):
            return choices[0]["message"]
        if "content" in payload or "tool_calls" in payload:
            return {
                "role": "assistant",
                "content": payload.get("content"),
                "tool_calls": payload.get("tool_calls") or [],
            }
        raise RuntimeError("capability gateway returned no assistant message")

    async def stream_complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        enable_thinking: bool | None = True,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Consume the backend's canonical LLM events without provider parsing."""

        async with self._client.stream(
            "POST",
            "llm/stream",
            json={
                "messages": messages,
                "tools": tools,
                "enable_thinking": enable_thinking,
                "scope": self._scope_payload(),
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                payload = __import__("json").loads(line)
                if not isinstance(payload, dict) or not isinstance(payload.get("type"), str):
                    raise RuntimeError("capability gateway returned an invalid LLM stream event")
                yield payload

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(
            f"tools/{name}",
            json={"arguments": arguments, "scope": self._scope_payload()},
        )
        response.raise_for_status()
        result = response.json()
        return result if isinstance(result, dict) else {"result": result}

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        await self.emit_many([(event_type, data)])

    async def emit_many(self, events: list[tuple[str, dict[str, Any]]]) -> None:
        if not events:
            return
        async with self._event_lock:
            previous = self._event_sequence
            payloads = []
            for event_type, data in events:
                self._event_sequence += 1
                payloads.append(
                    {
                        "sequence": self._event_sequence,
                        "type": event_type,
                        "payload": data,
                        "data": data,
                        "scope": self._scope_payload(),
                    }
                )
            try:
                response = await self._client.post(
                    "events/batch",
                    json={"events": payloads},
                    timeout=httpx.Timeout(60, connect=10),
                )
                response.raise_for_status()
            except Exception:
                self._event_sequence = previous
                raise

    async def inspect_image(
        self, file_path: str | Path, *, context: str = ""
    ) -> dict[str, Any]:
        path = Path(file_path)
        content = await asyncio.to_thread(path.read_bytes)
        response = await self._client.post(
            "visual-inspections",
            data={
                "context": context,
                "scope": __import__("json").dumps(self._scope_payload()),
            },
            files={"file": (path.name, content, _content_type(path))},
            timeout=httpx.Timeout(120, connect=10),
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {"analysis": str(payload)}

    async def upload_artifact(
        self,
        *,
        kind: str,
        file_path: str | Path,
        filename: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Copy an artifact out of the private named volume through the gateway."""

        path = Path(file_path)
        content = await asyncio.to_thread(path.read_bytes)
        response = await self._client.post(
            "artifacts",
            data={
                "kind": kind,
                "metadata": __import__("json").dumps(metadata or {}, ensure_ascii=False),
                "scope": __import__("json").dumps(self._scope_payload()),
            },
            files={"file": (filename or path.name, content, _content_type(path))},
            timeout=httpx.Timeout(300, connect=10),
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {"result": payload}

    async def list_sources(self) -> list[dict[str, Any]]:
        response = await self._client.get("sources")
        response.raise_for_status()
        payload = response.json()
        items = (
            payload.get("items", payload.get("sources", []))
            if isinstance(payload, dict)
            else payload
        )
        if not isinstance(items, list):
            raise TypeError("capability gateway returned an invalid source manifest")
        return [item for item in items if isinstance(item, dict)]

    async def download_source(self, source_id: str, destination: str | Path) -> Path:
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".part")
        async with self._client.stream("GET", f"sources/{quote(source_id, safe='')}") as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                async for chunk in response.aiter_bytes():
                    output.write(chunk)
        temporary.replace(path)
        return path

    async def download_asset(self, asset_id: str, destination: str | Path) -> Path:
        """Download a generated binary without ever placing base64 in LLM context."""

        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".part")
        async with self._client.stream("GET", f"assets/{quote(asset_id, safe='')}") as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                async for chunk in response.aiter_bytes():
                    output.write(chunk)
        temporary.replace(path)
        return path

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")
