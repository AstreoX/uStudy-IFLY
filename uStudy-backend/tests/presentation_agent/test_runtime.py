import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from presentation_agent.runner import _download_sources, _is_retryable_exception
from presentation_agent.runtime import AgentStreamError, PresentationAgentRuntime
from presentation_agent.skill_loader import SkillBundle


class FakeGateway:
    def __init__(self, replies):
        self.replies = list(replies)
        self.events = []
        self.uploads = []
        self.emit_many_calls = []
        self.scope = SimpleNamespace(run_id="run-test")
        self.event_sequence = 1

    async def emit(self, event_type, data):
        self.events.append((event_type, data))

    async def emit_many(self, events):
        self.emit_many_calls.append(events)
        self.events.extend(events)

    async def complete(self, messages, tools):
        self.last_messages = messages
        self.tools = tools
        return self.replies.pop(0)

    async def stream_complete(self, messages, tools, *, enable_thinking=True):
        self.last_messages = messages
        self.tools = tools
        message = self.replies.pop(0)
        for chunk in message.get("thinking_chunks", []):
            yield {"type": "thinking", "content": chunk}
        for chunk in message.get("content_chunks", [message.get("content", "")]):
            if chunk:
                yield {"type": "content", "content": chunk}
        for tool_call in message.get("tool_calls", []):
            function = tool_call.get("function") or tool_call
            arguments = function.get("arguments") or {}
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            yield {
                "type": "tool_call_start",
                "id": tool_call["id"],
                "name": function["name"],
            }
            yield {
                "type": "tool_call_end",
                "id": tool_call["id"],
                "name": function["name"],
                "arguments": arguments,
            }
        yield {
            "type": "done",
            "finish_reason": "tool_calls" if message.get("tool_calls") else "stop",
        }

    async def call_tool(self, name, arguments):
        return {"name": name, "arguments": arguments}

    async def upload_artifact(self, **kwargs):
        self.uploads.append(kwargs)
        return {"asset_id": f"asset-{kwargs['kind']}"}

    async def inspect_image(self, file_path, *, context=""):
        return {"ok": True, "passed": True, "summary": context or Path(file_path).name, "issues": []}


def make_skill(tmp_path: Path) -> SkillBundle:
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("Use the real presentation tool.", encoding="utf-8")
    return SkillBundle(skill, "Use the real presentation tool.", ())


def test_retry_classification_does_not_repeat_deterministic_runtime_failures():
    assert _is_retryable_exception(RuntimeError("gateway disconnected")) is True
    assert _is_retryable_exception(ValueError("invalid tool input")) is False
    assert (
        _is_retryable_exception(RuntimeError("maximum presentation-agent iterations reached"))
        is False
    )
    assert (
        _is_retryable_exception(
            AgentStreamError("account overdue", retryable=False, provider_code="Arrearage")
        )
        is False
    )


@pytest.mark.asyncio
@pytest.mark.skipif(os.name == "nt", reason="agent image executes commands under Linux bash")
async def test_execute_command_allows_arbitrary_code_inside_sandbox(tmp_path: Path):
    gateway = FakeGateway([])
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    runtime = PresentationAgentRuntime(
        gateway=gateway,
        skill=make_skill(tmp_path),
        workspace=workspace,
        instruction="test",
    )

    result = await runtime._execute_command(
        {"command": "python3 -c \"open('arbitrary.txt','w').write('allowed')\""}
    )

    assert result["ok"] is True
    assert (workspace / "arbitrary.txt").read_text() == "allowed"


@pytest.mark.asyncio
async def test_arbitrary_command_checkpoint_and_artifact_upload(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    gateway = FakeGateway(
        [
            {
                "content": "building",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "execute_command",
                            "arguments": json.dumps(
                                {
                                    "command": "mkdir -p output previews && printf ppt > output/final.pptx && printf png > output/slide-1.png"
                                }
                            ),
                        },
                    }
                ],
            },
            {"content": "done"},
        ]
    )
    runtime = PresentationAgentRuntime(
        gateway=gateway,
        skill=make_skill(tmp_path),
        workspace=workspace,
        instruction="make slides",
    )

    async def execute(arguments, **_kwargs):
        (workspace / "output").mkdir(parents=True, exist_ok=True)
        (workspace / "output" / "final.pptx").write_bytes(b"ppt")
        (workspace / "output" / "slide-1.png").write_bytes(b"png")
        return {"ok": True, "exit_code": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(runtime, "_execute_command", execute)
    monkeypatch.setattr(runtime, "_quality_gaps", lambda _previews: [])

    result = await runtime.run()

    assert result.read_bytes() == b"ppt"
    assert (workspace / ".presentation-agent" / "checkpoint.json").is_file()
    assert [item["kind"] for item in gateway.uploads] == ["pptx", "preview"]
    assert any(event[0] == "presentation_ready" for event in gateway.events)
    assert any(tool["function"]["name"] == "load_workspace_dependencies" for tool in gateway.tools)


@pytest.mark.asyncio
async def test_second_run_restores_prior_checkpoint(tmp_path: Path):
    workspace = tmp_path / "workspace"
    checkpoint = workspace / ".presentation-agent" / "checkpoint.json"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text(
        json.dumps({"messages": [{"role": "user", "content": "prior instruction"}]}),
        encoding="utf-8",
    )
    (workspace / "output").mkdir()
    (workspace / "output" / "final.pptx").write_bytes(b"ppt")
    gateway = FakeGateway([{"content": "updated"}])
    runtime = PresentationAgentRuntime(
        gateway=gateway,
        skill=make_skill(tmp_path),
        workspace=workspace,
        instruction="change slide five",
    )

    await runtime.run()

    contents = [message.get("content") for message in gateway.last_messages]
    assert "prior instruction" in contents
    assert "change slide five" in contents


@pytest.mark.asyncio
async def test_conversational_turn_without_pptx_completes_normally(tmp_path: Path):
    gateway = FakeGateway([{"content": "请先告诉我这节课的对象和时长。"}])
    runtime = PresentationAgentRuntime(
        gateway=gateway,
        skill=make_skill(tmp_path),
        workspace=tmp_path / "workspace",
        instruction="你好",
    )

    result = await runtime.run()

    assert result is None
    assert any(event[0] == "conversation_complete" for event in gateway.events)
    assert not any(event[0] == "blocked" for event in gateway.events)


@pytest.mark.asyncio
async def test_runtime_forwards_qwen_thinking_and_text_chunks_before_completion(tmp_path: Path):
    gateway = FakeGateway(
        [
            {
                "thinking_chunks": ["先看教案", "，再确认课时。"],
                "content_chunks": ["请告诉我", "这节课的时长。"],
            }
        ]
    )
    runtime = PresentationAgentRuntime(
        gateway=gateway,
        skill=make_skill(tmp_path),
        workspace=tmp_path / "workspace",
        instruction="帮我做课件",
    )

    await runtime.run()

    streamed = [item for item in gateway.events if item[0] in {"thinking_delta", "text_delta"}]
    assert [item[0] for item in streamed] == ["thinking_delta", "text_delta"]
    assert streamed[0][1]["content"] == "先看教案，再确认课时。"
    assert streamed[-1][1]["content"] == "请告诉我这节课的时长。"
    assert len(gateway.emit_many_calls) == 2


@pytest.mark.asyncio
async def test_runtime_emits_running_tool_card_before_done_and_followup_text(tmp_path: Path):
    gateway = FakeGateway(
        [
            {
                "content": "我先读取工具。",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "function": {"name": "load_workspace_dependencies", "arguments": "{}"},
                    }
                ],
            },
            {"content": "工具读取完成。"},
        ]
    )
    runtime = PresentationAgentRuntime(
        gateway=gateway,
        skill=make_skill(tmp_path),
        workspace=tmp_path / "workspace",
        instruction="检查环境",
    )

    await runtime.run()

    timeline = [
        (event_type, payload.get("status"), payload.get("content"))
        for event_type, payload in gateway.events
        if event_type in {"text_delta", "tool_call"}
    ]
    assert timeline == [
        ("text_delta", None, "我先读取工具。"),
        ("tool_call", "running", None),
        ("tool_call", "done", None),
        ("text_delta", None, "工具读取完成。"),
    ]


@pytest.mark.asyncio
async def test_generate_image_is_downloaded_and_base64_never_returns_to_llm(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    gateway = FakeGateway([])

    async def call_tool(name, arguments):
        return {
            "success": True,
            "image_base64": "huge-top-level-data",
            "data": {
                "asset_id": "asset-1",
                "filename": "figure.png",
                "image_base64": "huge-nested-data",
                "description": "linked list",
            },
        }

    async def download_asset(asset_id, destination):
        path = Path(destination)
        path.parent.mkdir(parents=True)
        path.write_bytes(b"png")
        return path

    gateway.call_tool = call_tool
    gateway.download_asset = download_asset
    runtime = PresentationAgentRuntime(
        gateway=gateway,
        skill=make_skill(tmp_path),
        workspace=workspace,
        instruction="test",
    )

    result = await runtime._call_tool("generate_image", {"description": "linked list"})

    assert "image_base64" not in result
    assert "image_base64" not in result["data"]
    assert Path(result["data"]["local_path"]).read_bytes() == b"png"


@pytest.mark.asyncio
async def test_run_sources_replace_stale_project_inputs_and_appear_in_prompt(tmp_path: Path):
    workspace = tmp_path / "workspace"
    stale = workspace / "input" / "old-template.pptx"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"old")

    class SourceGateway:
        async def list_sources(self):
            return [{"id": "source-1", "filename": "lesson.docx", "kind": "source"}]

        async def download_source(self, source_id, destination):
            path = Path(destination)
            path.write_bytes(b"new")
            return path

    sources = await _download_sources(SourceGateway(), str(workspace))
    runtime = PresentationAgentRuntime(
        gateway=FakeGateway([]),
        skill=make_skill(tmp_path),
        workspace=workspace,
        instruction="test",
        sources=sources,
    )

    prompt = runtime._system_prompt()
    assert not stale.exists()
    assert "kind=source" in prompt
    assert "lesson.docx" in prompt


@pytest.mark.asyncio
async def test_workspace_file_tools_are_atomic_and_path_scoped(tmp_path: Path):
    workspace = tmp_path / "workspace"
    runtime = PresentationAgentRuntime(
        gateway=FakeGateway([]),
        skill=make_skill(tmp_path),
        workspace=workspace,
        instruction="test",
    )

    written = await runtime._write_file({"path": "tmp/deck.mjs", "content": "const n = 1;\n"})
    read = await runtime._read_file({"path": "tmp/deck.mjs"})
    await runtime._write_file(
        {"path": "tmp/deck.mjs", "content": "export default n;\n", "append": True}
    )
    appended = await runtime._read_file({"path": "tmp/deck.mjs"})

    assert written["ok"] is True
    assert read["content"] == "const n = 1;\n"
    assert appended["content"] == "const n = 1;\nexport default n;\n"
    with pytest.raises(ValueError, match="inside /workspace"):
        await runtime._write_file({"path": "../escape.txt", "content": "no"})


@pytest.mark.asyncio
async def test_pending_tool_becomes_interrupted_result_after_restart(tmp_path: Path):
    workspace = tmp_path / "workspace"
    checkpoint = workspace / ".presentation-agent" / "checkpoint.json"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text(
        json.dumps(
            {
                "run_id": "run-test",
                "messages": [
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call-pending",
                                "type": "function",
                                "function": {"name": "execute_command", "arguments": "{}"},
                            }
                        ],
                    }
                ],
                "pending_tool": {
                    "id": "call-pending",
                    "name": "execute_command",
                    "arguments": {"command": "node tmp/deck.mjs"},
                },
            }
        ),
        encoding="utf-8",
    )
    gateway = FakeGateway([{"content": "我会先检查工作区。"}])
    runtime = PresentationAgentRuntime(
        gateway=gateway,
        skill=make_skill(tmp_path),
        workspace=workspace,
        instruction="继续",
    )

    await runtime.run()

    assert any(
        event_type == "tool_call"
        and payload.get("id") == "call-pending"
        and payload.get("error") == "interrupted_by_restart"
        for event_type, payload in gateway.events
    )
    assert any(
        message.get("tool_call_id") == "call-pending"
        and "interrupted_by_restart" in message.get("content", "")
        for message in gateway.last_messages
    )


def test_manual_resume_resets_exhausted_iteration_budget(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    checkpoint = workspace / ".presentation-agent" / "checkpoint.json"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text(
        json.dumps(
            {
                "run_id": "run-test",
                "iteration": 24,
                "stage": "assistant_received",
                "messages": [
                    {"role": "user", "content": "prior task"},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "inspect"},
                            {
                                "type": "image_url",
                                "image_url": {"url": "data:image/png;base64," + "x" * 1000},
                            },
                        ],
                    },
                ],
                "tool_ledger": {
                    "old": {
                        "name": "execute_command",
                        "arguments": {"command": "broken"},
                        "result": {"ok": False, "stderr": "x" * 1000},
                        "status": "error",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PRESENTATION_RESET_ITERATIONS", "1")
    runtime = PresentationAgentRuntime(
        gateway=FakeGateway([]),
        skill=make_skill(tmp_path),
        workspace=workspace,
        instruction="continue",
    )

    messages = runtime._load_messages()

    assert runtime._resume_iteration == 0
    assert "runtime environment has been repaired" in messages[-1]["content"]
    assert runtime._tool_ledger == {}
    assert all(message.get("role") != "tool" for message in messages)
    assert all("base64" not in str(message.get("content")) for message in messages)


def test_runtime_links_linux_artifact_dependencies_into_tmp(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "workspace"
    (workspace / "tmp").mkdir(parents=True)
    runtime_modules = tmp_path / "linux-node-modules"
    runtime_modules.mkdir()
    monkeypatch.setenv("RUNTIME_NODE_MODULES", str(runtime_modules))
    runtime = PresentationAgentRuntime(
        gateway=FakeGateway([]),
        skill=make_skill(tmp_path),
        workspace=workspace,
        instruction="test",
    )

    link = runtime._ensure_workspace_node_modules()

    assert link.is_symlink()
    assert link.resolve() == runtime_modules.resolve()


def test_identical_read_only_tool_calls_use_semantic_cache(tmp_path: Path):
    runtime = PresentationAgentRuntime(
        gateway=FakeGateway([]),
        skill=make_skill(tmp_path),
        workspace=tmp_path / "workspace",
        instruction="test",
    )
    runtime._tool_ledger["first"] = {
        "name": "read_skill_resource",
        "arguments": {"path": "style_guidelines.md"},
        "result": {"content": "large"},
        "status": "done",
    }

    hit = runtime._semantic_cache_hit(
        "read_skill_resource", {"path": "style_guidelines.md"}
    )

    assert hit is not None
    assert hit[0] == "first"


@pytest.mark.asyncio
async def test_class_summary_requires_explicit_teacher_request(tmp_path: Path):
    runtime = PresentationAgentRuntime(
        gateway=FakeGateway([]),
        skill=make_skill(tmp_path),
        workspace=tmp_path / "workspace",
        instruction="根据课程内容制作链表课件",
    )

    result = await runtime._call_tool("get_class_knowledge_summary", {})

    assert result["success"] is False
    assert "not explicitly requested" in result["error"]


@pytest.mark.asyncio
async def test_view_image_is_injected_into_same_main_model_context(tmp_path: Path):
    workspace = tmp_path / "workspace"
    image = workspace / "tmp" / "slide-1.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage-bytes")
    runtime = PresentationAgentRuntime(
        gateway=FakeGateway([]),
        skill=make_skill(tmp_path),
        workspace=workspace,
        instruction="make deck",
    )
    arguments = {"path": str(image), "context": "title slide"}

    result = await runtime._call_tool("view_image", arguments)
    followup = runtime._image_followup_message(arguments)

    assert result["ok"] is True
    assert followup["role"] == "user"
    assert followup["content"][0]["type"] == "text"
    assert followup["content"][1]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )
    messages = [followup]
    runtime._compact_consumed_images(messages)
    assert isinstance(messages[0]["content"], str)
    assert "inspected by the main model" in messages[0]["content"]
