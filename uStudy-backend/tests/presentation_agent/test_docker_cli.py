from unittest.mock import patch

import pytest

from presentation_agent.manager.docker_cli import (
    DockerCLI,
    DockerCommandError,
    DockerSandboxConfig,
    DockerUnavailable,
    build_docker_run_command,
    parse_du_bytes,
)
from presentation_agent.models import RunCreateRequest


def make_request(**overrides):
    values = {
        "run_id": "run-123",
        "project_id": "project-456",
        "user_id": "user-789",
        "space_id": "space-abc",
        "gateway_url": "http://backend:8000/api/internal/presentation-agent/runs/run-123",
        "capability_token": "x" * 32,
        "instruction": "根据教案制作课件",
    }
    values.update(overrides)
    return RunCreateRequest(**values)


def test_command_enforces_container_boundary_and_named_project_volume():
    config = DockerSandboxConfig(
        skill_host_dir="/opt/ustudy-skills/presentations",
        runtime_node_modules_host_dir="/opt/ustudy-runtime/node_modules",
        runtime_bin_host_dir="/opt/ustudy-runtime/bin",
    )

    command, created = build_docker_run_command(make_request(), config)
    joined = " ".join(command)

    assert command[:2] == ["docker", "run"]
    assert "--read-only" in command
    assert command[command.index("--user") + 1] == "10001:10001"
    assert "--cap-drop=ALL" in command
    assert "--security-opt=no-new-privileges:true" in command
    assert "--pids-limit" in command
    assert "--memory" in command
    assert "--cpus" in command
    assert "fsize=268435456:268435456" in command
    assert "--network" in command
    assert "ustudy-presentation-agent-internal" in command
    assert "type=volume,src=ustudy-presentation-project-456,dst=/workspace" in command
    assert "src=/opt/ustudy-skills/presentations,dst=/opt/skills/presentations,readonly" in joined
    assert "/opt/ustudy-runtime/node_modules" not in joined
    assert "/opt/ustudy-runtime/bin" not in joined
    assert "/var/run/docker.sock" not in joined
    assert "--privileged" not in command
    assert "--pid=host" not in command
    assert created.run_id == "run-123"
    assert "PRESENTATION_ATTEMPT=1" in command
    assert "PRESENTATION_MAX_ATTEMPTS=5" in command
    assert "PRESENTATION_MAX_ITERATIONS" not in joined
    assert "PRESENTATION_MAX_SECONDS" not in joined
    assert "PRESENTATION_RESET_ITERATIONS" not in joined


@pytest.mark.parametrize(
    "field,value",
    [("run_id", "../../escape"), ("project_id", "project;rm"), ("space_id", "space/name")],
)
def test_identifiers_reject_docker_argument_injection(field, value):
    with pytest.raises(ValueError):
        make_request(**{field: value})


def test_gateway_must_be_on_internal_allowlist():
    config = DockerSandboxConfig(skill_host_dir="/skills")
    with pytest.raises(ValueError, match="allowlist"):
        build_docker_run_command(
            make_request(gateway_url="http://attacker.example/gateway"), config
        )


def test_relative_skill_host_path_is_rejected():
    config = DockerSandboxConfig(skill_host_dir="./presentations")
    with pytest.raises(ValueError, match="absolute host path"):
        build_docker_run_command(make_request(), config)


def test_missing_docker_has_clear_failure():
    client = DockerCLI(DockerSandboxConfig(skill_host_dir="/skills"))
    with (
        patch("presentation_agent.manager.docker_cli.shutil.which", return_value=None),
        pytest.raises(DockerUnavailable, match="Docker CLI is unavailable"),
    ):
        client.ping()


def test_manager_accepts_backend_id_and_prompt_aliases():
    request = RunCreateRequest(
        id="run-123",
        project_id="project-456",
        user_id="user-789",
        space_id="space-abc",
        gateway_url="http://backend:8000/gateway/run-123",
        capability_token="x" * 32,
        prompt="制作课件",
    )

    assert request.run_id == "run-123"
    assert request.instruction == "制作课件"


@pytest.mark.parametrize(
    ("output", "expected"),
    [("12345\t/workspace\n", 12345), ("0 /workspace\n", 0)],
)
def test_parse_du_bytes(output, expected):
    assert parse_du_bytes(output) == expected


@pytest.mark.parametrize("output", ["", "not-a-number /workspace", "-1\t/workspace"])
def test_parse_du_bytes_rejects_invalid_output(output):
    with pytest.raises(DockerCommandError):
        parse_du_bytes(output)


def test_workspace_size_uses_read_only_du_exec(monkeypatch):
    client = DockerCLI(DockerSandboxConfig(skill_host_dir="/skills"))
    commands = []

    def fake_run(command, timeout=30):
        commands.append((command, timeout))
        return type("Result", (), {"stdout": "4096\t/workspace\n"})()

    monkeypatch.setattr(client, "_run", fake_run)

    assert client.workspace_size("ustudy-presentation-run-run-1") == 4096
    assert commands == [
        (
            [
                "docker",
                "exec",
                "ustudy-presentation-run-run-1",
                "/usr/bin/du",
                "-sb",
                "/workspace",
            ],
            30,
        )
    ]


def test_watcher_kills_running_container_over_workspace_limit(monkeypatch):
    config = DockerSandboxConfig(skill_host_dir="/skills", max_workspace_bytes=1024)
    client = DockerCLI(config)
    commands = []
    inspected = [
        {
            "Name": "/ustudy-presentation-run-run-1",
            "State": {"Status": "running"},
            "Config": {
                "Labels": {
                    "ustudy.presentation.created": "1000",
                    "ustudy.presentation.max-seconds": "900",
                }
            },
        }
    ]

    monkeypatch.setattr(
        client, "list_managed_containers", lambda: ["ustudy-presentation-run-run-1"]
    )

    def fake_run(command, timeout=30):
        commands.append(command)
        if command[:2] == ["docker", "inspect"]:
            import json

            return type("Result", (), {"stdout": json.dumps(inspected)})()
        return type("Result", (), {"stdout": ""})()

    monkeypatch.setattr(client, "_run", fake_run)
    monkeypatch.setattr(client, "workspace_size", lambda _: 1025)

    stopped = client.stop_expired_runs(1100)

    assert stopped == ["ustudy-presentation-run-run-1"]
    assert ["docker", "kill", "ustudy-presentation-run-run-1"] in commands
