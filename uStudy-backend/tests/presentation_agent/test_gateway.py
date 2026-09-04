import json
from pathlib import Path

import httpx
import pytest

from presentation_agent.gateway import CapabilityGateway
from presentation_agent.models import AgentScope


@pytest.mark.asyncio
async def test_gateway_adds_scope_and_bearer_to_llm_and_tool_calls(tmp_path: Path):
    requests = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/llm"):
            return httpx.Response(200, json={"message": {"role": "assistant", "content": "ok"}})
        return httpx.Response(200, json={"ok": True})

    scope = AgentScope(run_id="run-1", project_id="project-1", user_id="user-1", space_id="space-1")
    gateway = CapabilityGateway(
        base_url="http://backend/gateway/run-1",
        token="token",
        scope=scope,
        transport=httpx.MockTransport(handler),
    )
    try:
        message = await gateway.complete([{"role": "user", "content": "hi"}], [])
        result = await gateway.call_tool("get_course_graph_overview", {})
    finally:
        await gateway.close()

    assert message["content"] == "ok"
    assert result == {"ok": True}
    for request in requests:
        assert request.headers["authorization"] == "Bearer token"
        assert request.headers["x-presentation-run"] == "run-1"
        assert request.headers["x-presentation-project"] == "project-1"
    tool_body = json.loads(requests[1].content)
    assert tool_body["scope"]["user_id"] == "user-1"


@pytest.mark.asyncio
async def test_gateway_accepts_backend_direct_llm_shape_and_emits_sequence_two():
    bodies = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/llm"):
            return httpx.Response(
                200,
                json={
                    "content": "working",
                    "tool_calls": [{"id": "c1", "name": "execute_command", "arguments": {}}],
                    "finish_reason": "tool_calls",
                },
            )
        bodies.append(json.loads(request.content))
        return httpx.Response(202, json={"accepted": True})

    scope = AgentScope(run_id="run-1", project_id="project-1", user_id="user-1", space_id="space-1")
    gateway = CapabilityGateway(
        base_url="http://backend/gateway/run-1",
        token="token",
        scope=scope,
        transport=httpx.MockTransport(handler),
    )
    try:
        message = await gateway.complete([], [])
        await gateway.emit("run_started", {"stage": "started"})
    finally:
        await gateway.close()

    assert message["tool_calls"][0]["name"] == "execute_command"
    assert bodies[0]["events"][0]["sequence"] == 2
    assert bodies[0]["events"][0]["payload"] == {"stage": "started"}


@pytest.mark.asyncio
async def test_gateway_consumes_canonical_ndjson_llm_stream():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/llm/stream")
        return httpx.Response(
            200,
            headers={"content-type": "application/x-ndjson"},
            content=(
                b'{"type":"thinking","content":"thinking"}\n'
                b'{"type":"content","content":"answer"}\n'
                b'{"type":"tool_call_start","id":"c1","name":"execute_command"}\n'
                b'{"type":"tool_call_end","id":"c1","name":"execute_command","arguments":{}}\n'
                b'{"type":"done","finish_reason":"tool_calls"}\n'
            ),
        )

    scope = AgentScope(
        run_id="run-1", project_id="project-1", user_id="user-1", space_id="space-1"
    )
    gateway = CapabilityGateway(
        base_url="http://backend/gateway/run-1",
        token="token",
        scope=scope,
        transport=httpx.MockTransport(handler),
    )
    try:
        events = [event async for event in gateway.stream_complete([], [])]
    finally:
        await gateway.close()

    assert [event["type"] for event in events] == [
        "thinking",
        "content",
        "tool_call_start",
        "tool_call_end",
        "done",
    ]


@pytest.mark.asyncio
async def test_source_download_and_artifact_upload_are_binary(tmp_path: Path):
    seen_upload = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/sources"):
            return httpx.Response(200, json={"items": [{"id": "s1", "filename": "lesson.txt"}]})
        if request.url.path.endswith("/sources/s1"):
            return httpx.Response(200, content=b"lesson bytes")
        if request.url.path.endswith("/artifacts"):
            seen_upload["content_type"] = request.headers["content-type"]
            seen_upload["body"] = request.content
            return httpx.Response(200, json={"asset_id": "a1"})
        raise AssertionError(request.url)

    scope = AgentScope(run_id="run-1", project_id="project-1", user_id="user-1", space_id="space-1")
    gateway = CapabilityGateway(
        base_url="http://backend/gateway/run-1",
        token="token",
        scope=scope,
        transport=httpx.MockTransport(handler),
    )
    try:
        assert (await gateway.list_sources())[0]["id"] == "s1"
        downloaded = await gateway.download_source("s1", tmp_path / "lesson.txt")
        result = await gateway.upload_artifact(kind="pptx", file_path=downloaded)
    finally:
        await gateway.close()

    assert downloaded.read_bytes() == b"lesson bytes"
    assert result == {"asset_id": "a1"}
    assert seen_upload["content_type"].startswith("multipart/form-data;")
    assert b"lesson bytes" in seen_upload["body"]


@pytest.mark.asyncio
async def test_gateway_syncs_sequence_and_uploads_visual_inspection(tmp_path: Path):
    seen = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/state"):
            return httpx.Response(200, json={"last_sequence": 41, "status": "recovering"})
        if request.url.path.endswith("/visual-inspections"):
            return httpx.Response(
                200,
                json={"ok": True, "passed": True, "summary": "layout ok", "issues": []},
            )
        return httpx.Response(202, json={"accepted": True})

    image = tmp_path / "slide-1.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    gateway = CapabilityGateway(
        base_url="http://backend/gateway/run-1",
        token="token",
        scope=AgentScope(
            run_id="run-1", project_id="project-1", user_id="user-1", space_id="space-1"
        ),
        transport=httpx.MockTransport(handler),
    )
    try:
        state = await gateway.sync_state()
        await gateway.emit("run_started", {})
        inspection = await gateway.inspect_image(image, context="slide one")
    finally:
        await gateway.close()

    assert state["last_sequence"] == 41
    event_body = json.loads(seen[1].content)
    assert event_body["events"][0]["sequence"] == 42
    assert inspection["passed"] is True
    assert seen[2].headers["content-type"].startswith("multipart/form-data;")
