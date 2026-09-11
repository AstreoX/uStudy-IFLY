"""Container entry point for a single presentation-agent run."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import shutil
import sys
import traceback
from uuid import uuid4

import httpx

from presentation_agent.gateway import CapabilityGateway
from presentation_agent.models import AgentScope
from presentation_agent.runtime import PresentationAgentRuntime
from presentation_agent.skill_loader import (
    PresentationSkillLoader,
    SkillUnavailable,
    validate_presentation_runtime,
)


def _required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"missing required environment variable {name}")
    return value


def _decode_instruction() -> str:
    encoded = _required("PRESENTATION_INSTRUCTION_B64")
    return base64.b64decode(encoded, validate=True).decode("utf-8")


async def _emit_direct(gateway: CapabilityGateway, event_type: str, data: dict) -> None:
    try:
        await gateway.emit(event_type, data)
    except Exception:  # noqa: BLE001 - last-resort stderr reporting if the gateway is down
        print(json.dumps({"type": event_type, "data": data}, ensure_ascii=False), file=sys.stderr)


def _safe_source_filename(source_id: str, filename: str, used: set[str]) -> str:
    name = os.path.basename(filename.replace("\\", "/")).strip()
    name = re.sub(r"[^\w.()\-\u4e00-\u9fff ]+", "_", name, flags=re.UNICODE)
    if not name or name in (".", ".."):
        name = "source"
    if name in used:
        prefix = re.sub(r"[^A-Za-z0-9_-]", "_", source_id)[:24] or "source"
        name = f"{prefix}-{name}"
    used.add(name)
    return name


async def _download_sources(gateway: CapabilityGateway, workspace: str) -> list[dict]:
    input_dir = os.path.join(workspace, "input")
    # The named project volume survives between runs, but the input set is
    # revision-scoped. Never let a removed lesson plan/template leak into the
    # next turn's prompt.
    if os.path.islink(input_dir) or os.path.isfile(input_dir):
        os.unlink(input_dir)
    else:
        shutil.rmtree(input_dir, ignore_errors=True)
    os.makedirs(input_dir, exist_ok=True)
    manifest = await gateway.list_sources()
    used: set[str] = set()
    downloaded: list[dict] = []
    for source in manifest:
        source_id = str(source.get("id", ""))
        if not source_id:
            continue
        filename = _safe_source_filename(source_id, str(source.get("filename") or "source"), used)
        destination = os.path.join(workspace, "input", filename)
        path = await gateway.download_source(source_id, destination)
        downloaded.append(
            {
                "id": source_id,
                "kind": source.get("kind"),
                "path": str(path),
                "filename": filename,
                "size": path.stat().st_size,
            }
        )
    return downloaded


def _is_retryable_exception(exc: Exception) -> bool:
    explicit = getattr(exc, "retryable", None)
    if isinstance(explicit, bool):
        return explicit
    if isinstance(exc, (ValueError, TypeError, PermissionError, FileNotFoundError)):
        return False
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
        return False
    if "maximum presentation-agent iterations reached" in str(exc):
        return False
    return True


async def main() -> int:
    scope = AgentScope(
        run_id=_required("PRESENTATION_RUN_ID"),
        project_id=_required("PRESENTATION_PROJECT_ID"),
        user_id=_required("PRESENTATION_USER_ID"),
        space_id=_required("PRESENTATION_SPACE_ID"),
    )
    gateway = CapabilityGateway(
        base_url=_required("PRESENTATION_GATEWAY_URL"),
        token=_required("PRESENTATION_CAPABILITY_TOKEN"),
        scope=scope,
    )
    stage = "gateway_sync"
    try:
        await gateway.sync_state()
        skill_root = os.environ.get("SKILL_DIR", "/opt/skills/presentations")
        workspace = os.environ.get("PRESENTATION_WORKSPACE", "/workspace")
        stage = "runtime_validation"
        for directory in (".home", ".tmp", "tmp", "output", "assets"):
            os.makedirs(os.path.join(workspace, directory), exist_ok=True)
        blockers = validate_presentation_runtime(
            skill_root=skill_root,
            runtime_node=os.environ.get("RUNTIME_NODE", "/usr/bin/node"),
            runtime_node_modules=os.environ.get("RUNTIME_NODE_MODULES", "/opt/runtime/node_modules"),
            runtime_bin_dir=os.environ.get("RUNTIME_BIN_DIR", "/opt/runtime/bin"),
        )
        if blockers:
            await _emit_direct(
                gateway,
                "blocked",
                {
                    "message": "PPT Agent 运行依赖不完整",
                    "reason": "runtime_dependencies",
                    "error_code": "runtime_dependencies",
                    "retryable": False,
                    "recoverable": False,
                    "details": blockers,
                },
            )
            return 78
        try:
            skill = PresentationSkillLoader(skill_root).load()
        except SkillUnavailable as exc:
            await _emit_direct(
                gateway, "blocked", {"message": str(exc), "error_code": "runtime_dependencies", "retryable": False, "recoverable": False}
            )
            return 78
        await gateway.emit(
            "skill_loaded", {"root": str(skill.root), "resource_count": len(skill.resources)}
        )
        stage = "source_download"
        sources = await _download_sources(gateway, workspace)
        await gateway.emit("sources_ready", {"sources": sources})
        runtime = PresentationAgentRuntime(
            gateway=gateway,
            skill=skill,
            workspace=workspace,
            instruction=_decode_instruction(),
            sources=sources,
        )
        stage = "agent_runtime"
        await runtime.run()
        return 0
    except Exception as exc:  # noqa: BLE001 - container boundary converts all failures to events
        attempt = int(os.environ.get("PRESENTATION_ATTEMPT", "1"))
        max_attempts = int(os.environ.get("PRESENTATION_MAX_ATTEMPTS", "5"))
        trace_id = uuid4().hex
        detail = str(exc).strip() or exc.__class__.__name__
        retryable = attempt < max_attempts and _is_retryable_exception(exc)
        payload = {
            "message": detail,
            "detail": detail,
            "error_type": exc.__class__.__name__,
            "stage": stage,
            "retryable": retryable,
            "recoverable": _is_retryable_exception(exc),
            "error_code": "agent_execution_failed",
            "attempt": attempt,
            "max_attempts": max_attempts,
            "trace_id": trace_id,
        }
        for key in ("status_code", "provider_code"):
            value = getattr(exc, key, None)
            if value is not None:
                payload[key] = value
        upstream_error_type = getattr(exc, "error_type", None)
        if upstream_error_type:
            payload["upstream_error_type"] = upstream_error_type
        print(
            json.dumps(
                {**payload, "traceback": traceback.format_exc()}, ensure_ascii=False
            ),
            file=sys.stderr,
        )
        if retryable:
            await _emit_direct(gateway, "attempt_failed", payload)
            return 75
        await _emit_direct(gateway, "error", payload)
        return 78 if not _is_retryable_exception(exc) else 1
    finally:
        await gateway.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
