"""Safe argument-list construction and Docker CLI adapter.

The manager is the only service that receives the Docker socket.  Child agent
containers are never given that socket or another host-control capability.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from urllib.parse import urlparse

from presentation_agent.models import RunCreated, RunCreateRequest, RunStatus


class DockerUnavailable(RuntimeError):
    pass


class DockerCommandError(RuntimeError):
    pass


@dataclass(frozen=True)
class SandboxLimits:
    memory: str = "1536m"
    cpus: str = "2.0"
    pids: int = 256
    stop_timeout_seconds: int = 10
    max_file_bytes: int = 268_435_456


@dataclass(frozen=True)
class DockerSandboxConfig:
    image: str = "ustudy-presentation-agent:local"
    network: str = "ustudy-presentation-agent-internal"
    skill_host_dir: str | None = None
    runtime_node_modules_host_dir: str | None = None
    runtime_bin_host_dir: str | None = None
    allowed_gateway_hosts: tuple[str, ...] = ("backend", "ustudy-backend", "ustudy-dev-backend")
    container_retention_seconds: int = 3600
    max_workspace_bytes: int = 2_147_483_648
    limits: SandboxLimits = SandboxLimits()

    @classmethod
    def from_env(cls) -> DockerSandboxConfig:
        hosts = tuple(
            host.strip()
            for host in os.environ.get(
                "PRESENTATION_GATEWAY_ALLOWED_HOSTS", "backend,ustudy-backend,ustudy-dev-backend"
            ).split(",")
            if host.strip()
        )
        return cls(
            image=os.environ.get("PRESENTATION_AGENT_IMAGE", "ustudy-presentation-agent:local"),
            network=os.environ.get(
                "PRESENTATION_AGENT_NETWORK", "ustudy-presentation-agent-internal"
            ),
            skill_host_dir=os.environ.get("PRESENTATION_SKILL_HOST_DIR") or None,
            runtime_node_modules_host_dir=os.environ.get(
                "PRESENTATION_RUNTIME_NODE_MODULES_HOST_DIR"
            )
            or None,
            runtime_bin_host_dir=os.environ.get("PRESENTATION_RUNTIME_BIN_HOST_DIR") or None,
            allowed_gateway_hosts=hosts,
            container_retention_seconds=int(
                os.environ.get("PRESENTATION_AGENT_CONTAINER_RETENTION_SECONDS", "3600")
            ),
            max_workspace_bytes=int(
                os.environ.get("PRESENTATION_AGENT_MAX_WORKSPACE_BYTES", "2147483648")
            ),
            limits=SandboxLimits(
                memory=os.environ.get("PRESENTATION_AGENT_MEMORY", "1536m"),
                cpus=os.environ.get("PRESENTATION_AGENT_CPUS", "2.0"),
                pids=int(os.environ.get("PRESENTATION_AGENT_PIDS", "256")),
                stop_timeout_seconds=int(
                    os.environ.get("PRESENTATION_AGENT_STOP_TIMEOUT_SECONDS", "10")
                ),
                max_file_bytes=int(
                    os.environ.get("PRESENTATION_AGENT_MAX_FILE_BYTES", "268435456")
                ),
            ),
        )


def _resource_suffix(value: str, max_length: int = 96) -> str:
    return value.lower()[:max_length]


def container_name(run_id: str) -> str:
    return f"ustudy-presentation-run-{_resource_suffix(run_id)}"


def workspace_volume(project_id: str) -> str:
    return f"ustudy-presentation-{_resource_suffix(project_id)}"


def _bind_mount(source: str, destination: str) -> str:
    if not source:
        raise ValueError(f"host source for {destination} is empty")
    # Source is interpreted by the Docker daemon, not relative to the manager
    # container.  Requiring an absolute host path prevents that common error.
    is_windows_absolute = len(source) >= 3 and source[1:3] in (":\\", ":/")
    if not (PurePosixPath(source).is_absolute() or is_windows_absolute):
        raise ValueError(f"Docker bind source must be an absolute host path: {source}")
    if any(character in source for character in (",", "\n", "\r")):
        raise ValueError("Docker bind source contains unsupported characters")
    return f"type=bind,src={source},dst={destination},readonly"


def validate_gateway_url(url: str, allowed_hosts: tuple[str, ...]) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "http":
        raise ValueError("sandbox gateway must use HTTP on the internal Docker network")
    if not parsed.hostname or parsed.hostname not in allowed_hosts:
        raise ValueError(f"gateway host is not on the allowlist: {parsed.hostname!r}")


def parse_du_bytes(output: str) -> int:
    """Parse the byte count emitted by GNU ``du -sb``."""

    first_line = output.splitlines()[0] if output.splitlines() else ""
    first_field = first_line.split(maxsplit=1)[0] if first_line else ""
    try:
        value = int(first_field)
    except ValueError as exc:
        raise DockerCommandError(f"invalid workspace size response: {output[:200]!r}") from exc
    if value < 0:
        raise DockerCommandError("workspace size cannot be negative")
    return value


def build_docker_run_command(
    request: RunCreateRequest, config: DockerSandboxConfig
) -> tuple[list[str], RunCreated]:
    """Build a non-shell Docker command with the complete isolation policy."""

    validate_gateway_url(str(request.gateway_url), config.allowed_gateway_hosts)
    if not config.skill_host_dir:
        raise ValueError(
            "PRESENTATION_SKILL_HOST_DIR must be the daemon-visible absolute path "
            "of the pinned mature presentation skill"
        )
    name = container_name(request.run_id)
    volume = workspace_volume(request.project_id)
    instruction = base64.b64encode(request.instruction.encode("utf-8")).decode("ascii")
    created_epoch = int(datetime.now(timezone.utc).timestamp())
    command = [
        "docker",
        "run",
        "--detach",
        "--name",
        name,
        "--init",
        "--user",
        "10001:10001",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        "--pids-limit",
        str(config.limits.pids),
        "--memory",
        config.limits.memory,
        "--cpus",
        config.limits.cpus,
        "--ulimit",
        f"fsize={config.limits.max_file_bytes}:{config.limits.max_file_bytes}",
        "--ulimit",
        "nofile=1024:1024",
        "--network",
        config.network,
        "--restart",
        "no",
        "--stop-timeout",
        str(config.limits.stop_timeout_seconds),
        "--mount",
        f"type=volume,src={volume},dst=/workspace",
        "--mount",
        _bind_mount(config.skill_host_dir, "/opt/skills/presentations"),
        "--label",
        "ustudy.presentation-agent=true",
        "--label",
        f"ustudy.presentation.run-id={request.run_id}",
        "--label",
        f"ustudy.presentation.project-id={request.project_id}",
        "--label",
        f"ustudy.presentation.created={created_epoch}",
        "--label",
        f"ustudy.presentation.attempt={request.attempt}",
        "--label",
        f"ustudy.presentation.max-attempts={request.max_attempts}",
    ]
    # Node dependencies and native helper binaries are baked into the Linux
    # agent image. Host runtime mounts are intentionally forbidden because a
    # Windows node_modules tree contains incompatible native addons.
    environment = {
        "HOME": "/workspace/.home",
        "TMPDIR": "/workspace/.tmp",
        "PYTHONDONTWRITEBYTECODE": "1",
        "SKILL_DIR": "/opt/skills/presentations",
        "RUNTIME_NODE": "/usr/local/bin/node",
        "RUNTIME_NODE_MODULES": "/opt/runtime/node_modules",
        "RUNTIME_BIN_DIR": "/opt/runtime/bin",
        "PRESENTATION_WORKSPACE": "/workspace",
        "PRESENTATION_RUN_ID": request.run_id,
        "PRESENTATION_PROJECT_ID": request.project_id,
        "PRESENTATION_USER_ID": request.user_id,
        "PRESENTATION_SPACE_ID": request.space_id,
        "PRESENTATION_GATEWAY_URL": str(request.gateway_url).rstrip("/"),
        "PRESENTATION_CAPABILITY_TOKEN": request.capability_token,
        "PRESENTATION_INSTRUCTION_B64": instruction,
        "PRESENTATION_ATTEMPT": str(request.attempt),
        "PRESENTATION_MAX_ATTEMPTS": str(request.max_attempts),
    }
    for key, value in environment.items():
        command.extend(["--env", f"{key}={value}"])
    command.append(config.image)
    return command, RunCreated(
        run_id=request.run_id,
        project_id=request.project_id,
        container_name=name,
        workspace_volume=volume,
    )


class DockerCLI:
    def __init__(self, config: DockerSandboxConfig | None = None) -> None:
        self.config = config or DockerSandboxConfig.from_env()

    def _run(self, args: Sequence[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
        if shutil.which("docker") is None:
            raise DockerUnavailable(
                "Docker CLI is unavailable; the presentation sandbox manager requires "
                "Docker Engine access through /var/run/docker.sock"
            )
        try:
            result = subprocess.run(
                list(args), capture_output=True, text=True, timeout=timeout, check=False
            )
        except FileNotFoundError as exc:
            raise DockerUnavailable("Docker CLI executable was not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise DockerUnavailable("Docker daemon did not respond before the timeout") from exc
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise DockerCommandError(stderr or "Docker command failed")
        return result

    def ping(self) -> None:
        self._run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=10)

    def create_run(self, request: RunCreateRequest) -> RunCreated:
        command, created = build_docker_run_command(request, self.config)
        # Explicit volume creation makes project persistence independent from a
        # container's lifecycle. Docker volume names are derived only from
        # validated project IDs.
        self._run(["docker", "volume", "create", created.workspace_volume])
        # On failure, never delete the volume: it may contain a previous revision.
        self._run(command, timeout=60)
        return created

    def inspect_run(self, run_id: str, *, cancelled: bool = False) -> RunStatus:
        name = container_name(run_id)
        result = self._run(["docker", "inspect", name])
        data = json.loads(result.stdout)[0]
        state = data.get("State", {})
        labels = data.get("Config", {}).get("Labels", {}) or {}
        raw = state.get("Status")
        exit_code = state.get("ExitCode") if raw == "exited" else None
        if cancelled:
            status = "cancelled"
        elif raw in ("created", "restarting"):
            status = "starting"
        elif raw == "running":
            status = "running"
        elif raw == "exited" and exit_code == 0:
            status = "succeeded"
        elif raw in ("exited", "dead", "removing"):
            status = "failed"
        else:
            status = "unknown"
        return RunStatus(
            run_id=run_id,
            project_id=labels.get("ustudy.presentation.project-id"),
            container_name=name,
            status=status,
            attempt=int(labels.get("ustudy.presentation.attempt") or 1),
            max_attempts=int(labels.get("ustudy.presentation.max-attempts") or 5),
            exit_code=exit_code,
            started_at=state.get("StartedAt") or None,
            finished_at=state.get("FinishedAt") or None,
            error=state.get("Error") or None,
        )

    def cancel_run(self, run_id: str) -> None:
        self._run(["docker", "stop", "--time", "10", container_name(run_id)], timeout=20)

    def remove_run(self, run_id: str) -> None:
        """Remove only the disposable container; the named workspace volume survives."""

        self._run(["docker", "rm", "--force", container_name(run_id)], timeout=20)

    def list_managed_containers(self) -> list[str]:
        result = self._run(
            [
                "docker",
                "ps",
                "--all",
                "--filter",
                "label=ustudy.presentation-agent=true",
                "--format",
                "{{.Names}}",
            ]
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    def workspace_size(self, container: str) -> int:
        if not container.startswith("ustudy-presentation-run-"):
            raise ValueError("not a managed presentation container")
        result = self._run(
            ["docker", "exec", container, "/usr/bin/du", "-sb", "/workspace"],
            timeout=30,
        )
        return parse_du_bytes(result.stdout)

    def stop_expired_runs(self, now_epoch: int) -> list[str]:
        """Enforce workspace limits and retire finished containers, preserving volumes."""
        names = self.list_managed_containers()
        if not names:
            return []
        result = self._run(["docker", "inspect", *names])
        stopped: list[str] = []
        for item in json.loads(result.stdout):
            state = item.get("State", {})
            name = item.get("Name", "").lstrip("/")
            if not name.startswith("ustudy-presentation-run-"):
                continue
            if state.get("Status") == "running":
                try:
                    used_bytes = self.workspace_size(name)
                except DockerCommandError:
                    continue  # The container may have exited since inspect.
                if used_bytes > self.config.max_workspace_bytes:
                    self._run(["docker", "kill", name], timeout=15)
                    stopped.append(name)
            elif state.get("Status") in {"exited", "dead"}:
                try:
                    finished = datetime.fromisoformat(
                        state["FinishedAt"].replace("Z", "+00:00")
                    ).timestamp()
                except (KeyError, TypeError, ValueError, OverflowError):
                    continue
                if finished > 0 and now_epoch > finished + self.config.container_retention_seconds:
                    self._run(["docker", "rm", name], timeout=15)
        return stopped
