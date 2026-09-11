import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from presentation_agent import runner
from presentation_agent.manager import app as manager
from presentation_agent.manager.docker_cli import DockerCLI, DockerSandboxConfig
from presentation_agent.models import RunCreateRequest, RunStatus
from presentation_agent.runtime import PresentationAgentRuntime
from tests.presentation_agent.test_runtime import FakeGateway, make_skill


def call(identifier, name, arguments):
    return {"tool_calls": [{"id": identifier, "function": {"name": name, "arguments": arguments}}]}


@pytest.mark.asyncio
async def test_more_than_120_read_turns_then_delivers_without_correction(tmp_path):
    gateway = FakeGateway([
        *[call(f"read-{i}", "load_workspace_dependencies", {}) for i in range(125)],
        call("write", "execute_command", {
            "command": "mkdir -p output; printf ppt > output/final.pptx; printf png > output/slide-1.png; "
            "true mark_artifact_operation_started.mjs slides_test.py"
        }),
        call("inspect", "view_image", {"path": "output/slide-1.png"}),
        {"content": "done"},
    ])
    runtime = PresentationAgentRuntime(gateway=gateway, skill=make_skill(tmp_path),
                                       workspace=tmp_path / "workspace", instruction="make deck", max_iterations=1)
    # Real artifact/preview existence and the production QA gate are used; the
    # shell builds tiny fixture files rather than invoking a paid model.
    async def fixture_build(*args, **kwargs):
        (runtime.workspace / "output/final.pptx").write_bytes(b"fixture-ppt")
        (runtime.workspace / "output/slide-1.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")
        return {"ok": True}
    runtime._execute_command = fixture_build
    result = await runtime.run()
    assert result.is_file()
    assert [x["kind"] for x in gateway.uploads] == ["pptx", "preview"]
    checkpoint = json.loads(runtime.checkpoint_path.read_text())
    assert checkpoint["iteration"] == 128
    user_messages = [m["content"] for m in gateway.last_messages if m["role"] == "user"]
    assert user_messages == ["make deck", "[A rendered slide image was inspected by the main model in the immediately following turn.]"]


@pytest.mark.asyncio
async def test_same_run_existing_deck_is_delivered_after_resume(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / "output").mkdir(parents=True)
    (workspace / "output/final.pptx").write_bytes(b"ppt")
    (workspace / "output/slide-1.png").write_bytes(b"png")
    checkpoint = workspace / ".presentation-agent/checkpoint.json"
    checkpoint.parent.mkdir()
    checkpoint.write_text(json.dumps({
        "run_id": "run-test", "iteration": 60, "stage": "tool_completed",
        "messages": [{"role": "user", "content": "original task"}],
        "tool_ledger": {
            "build": {"name": "execute_command", "arguments": {"command": "mark_artifact_operation_started.mjs slides_test.py"}, "result": {"ok": True}},
            "inspect": {"name": "view_image", "arguments": {"path": "output/slide-1.png"}, "result": {"ok": True}},
        },
    }))
    gateway = FakeGateway([{"content": "done"}])
    runtime = PresentationAgentRuntime(gateway=gateway, skill=make_skill(tmp_path), workspace=workspace, instruction="same task")
    assert await runtime.run() == workspace / "output/final.pptx"
    assert json.loads(checkpoint.read_text())["iteration"] == 61
    assert len(gateway.uploads) == 2


@pytest.mark.asyncio
async def test_runner_ignores_legacy_limits_even_after_eight_hours(tmp_path, monkeypatch):
    for name in ("RUN_ID", "PROJECT_ID", "USER_ID", "SPACE_ID"):
        monkeypatch.setenv(f"PRESENTATION_{name}", "test")
    monkeypatch.setenv("PRESENTATION_GATEWAY_URL", "http://backend/runs/test")
    monkeypatch.setenv("PRESENTATION_CAPABILITY_TOKEN", "x" * 32)
    monkeypatch.setenv("PRESENTATION_INSTRUCTION_B64", "dGVzdA==")
    monkeypatch.setenv("PRESENTATION_WORKSPACE", str(tmp_path / "workspace"))
    monkeypatch.setenv("PRESENTATION_MAX_SECONDS", "1")
    monkeypatch.setenv("PRESENTATION_MAX_ITERATIONS", "1")
    gateway = FakeGateway([])
    async def sync(): return {}
    async def close(): pass
    gateway.sync_state, gateway.close = sync, close
    monkeypatch.setattr(runner, "CapabilityGateway", lambda **kw: gateway)
    monkeypatch.setattr(runner, "validate_presentation_runtime", lambda **kw: [])
    monkeypatch.setattr(runner, "PresentationSkillLoader", lambda root: SimpleNamespace(load=lambda: make_skill(tmp_path)))
    async def sources(*args): return []
    monkeypatch.setattr(runner, "_download_sources", sources)
    # A fake loop clock is restored before pytest resumes its own scheduling.
    async def long_run():
        with monkeypatch.context() as clock:
            clock.setattr(runner.asyncio.get_running_loop(), "time", lambda: 8 * 3600.0)
    monkeypatch.setattr(runner, "PresentationAgentRuntime", lambda **kw: SimpleNamespace(run=long_run))
    async def no_task_timeout(*args, **kwargs):
        raise AssertionError("runner must not install a whole-task timeout")
    monkeypatch.setattr(runner.asyncio, "wait_for", no_task_timeout)
    assert await runner.main() == 0


def test_manager_retries_after_legacy_deadline_but_keeps_attempt_budget():
    request = RunCreateRequest(run_id="run", project_id="project", user_id="user", space_id="space",
                               gateway_url="http://backend/runs/run", capability_token="x" * 32,
                               instruction="make deck", max_iterations=60, max_seconds=1800)
    state = {"request": request.model_dump(), "deadline_at": 1800, "attempt": 1}
    status = RunStatus(run_id="run", container_name="test", status="failed", exit_code=75)
    assert manager._is_retryable(state, status, 8 * 3600)
    assert "max_seconds" not in manager._request_for_attempt(state, 2).model_dump()
    state["attempt"] = 5
    assert not manager._is_retryable(state, status, 8 * 3600)


@pytest.mark.asyncio
async def test_cancellation_stops_container_and_prevents_retry(tmp_path, monkeypatch):
    stopped = []
    monkeypatch.setattr(manager, "STATE_DIR", tmp_path)
    monkeypatch.setattr(manager, "docker", SimpleNamespace(
        cancel_run=lambda run_id: stopped.append(run_id),
        inspect_run=lambda run_id, **kw: RunStatus(run_id=run_id, container_name="test", status="cancelled"),
    ))
    result = await manager.cancel_run("run")
    assert result.status == "cancelled" and stopped == ["run"]
    request = RunCreateRequest(run_id="run", project_id="project", user_id="user", space_id="space",
                               gateway_url="http://backend/runs/run", capability_token="x" * 32, instruction="make deck")
    state = {"request": request.model_dump(), "attempt": 1}
    status = RunStatus(run_id="run", container_name="test", status="failed", exit_code=75)
    assert not manager._is_retryable(state, status, 8 * 3600)


def test_container_age_does_not_kill_and_cleanup_uses_finished_at(monkeypatch):
    client = DockerCLI(DockerSandboxConfig(skill_host_dir="/skills", container_retention_seconds=3600))
    now = 100000
    def item(name, state, finished):
        return {"Name": f"/ustudy-presentation-run-{name}", "State": {"Status": state, "FinishedAt": datetime.fromtimestamp(finished, timezone.utc).isoformat()},
                "Config": {"Labels": {"ustudy.presentation.created": "1", "ustudy.presentation.max-seconds": "1800"}}}
    entries = [item("running", "running", 0), item("recent", "exited", now - 60), item("old", "exited", now - 3601)]
    commands = []
    monkeypatch.setattr(client, "list_managed_containers", lambda: [x["Name"].lstrip("/") for x in entries])
    monkeypatch.setattr(client, "workspace_size", lambda name: 1)
    def execute(command, **kw):
        commands.append(command)
        return SimpleNamespace(stdout=json.dumps(entries))
    monkeypatch.setattr(client, "_run", execute)
    assert client.stop_expired_runs(now) == []
    assert [x for x in commands if x[1] != "inspect"] == [["docker", "rm", "ustudy-presentation-run-old"]]
