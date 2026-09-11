"""Small, provider-neutral tool-calling loop executed inside the sandbox."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import signal
import tempfile
import time
from itertools import count
from pathlib import Path
from typing import Any

from presentation_agent.gateway import CapabilityGateway
from presentation_agent.skill_loader import PresentationSkillLoader, SkillBundle

HOST_CAPABILITIES = (
    "get_course_graph_overview",
    "list_documents",
    "search_keywords",
    "read_document",
    "view_document_page",
    "get_class_knowledge_summary",
    "generate_image",
    "publish_presentation_to_space",
)

SEMANTIC_CACHE_TOOLS = {
    "get_course_graph_overview",
    "list_documents",
    "search_keywords",
    "read_document",
    "view_document_page",
    "get_class_knowledge_summary",
    "read_skill_resource",
    "read_file",
    "load_workspace_dependencies",
    "view_image",
}


class AgentStreamError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool,
        status_code: int | None = None,
        provider_code: str | None = None,
        error_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code
        self.provider_code = provider_code
        self.error_type = error_type


def _function_tool(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties},
        },
    }


LOCAL_TOOLS = (
    _function_tool(
        "load_workspace_dependencies",
        "Return the exact presentation runtime paths provisioned by the sandbox host. "
        "Call this before presentation builders, as required by the mounted skill.",
        {},
    ),
    _function_tool(
        "read_file",
        "Read a UTF-8 text file from the writable project workspace. Use this to inspect "
        "generated .mjs and QA files without shell quoting.",
        {
            "path": {"type": "string"},
            "offset": {"type": "integer", "minimum": 0},
            "limit": {"type": "integer", "minimum": 1, "maximum": 200000},
        },
    ),
    _function_tool(
        "write_file",
        "Atomically write or append a UTF-8 file inside the project workspace. Prefer this "
        "over shell heredocs. Keep each content chunk under 20000 characters and use append=true "
        "for later chunks of large presentation builders.",
        {
            "path": {"type": "string"},
            "content": {"type": "string", "maxLength": 20000},
            "append": {"type": "boolean"},
        },
    ),
    _function_tool(
        "apply_patch",
        "Apply unified diff hunks to one existing workspace file. Pass only @@ hunks "
        "without ---/+++ file headers.",
        {"path": {"type": "string"}, "patch": {"type": "string"}},
    ),
    _function_tool(
        "execute_command",
        "Execute an arbitrary shell command inside the isolated project sandbox. Use this "
        "for authoring, rendering, inspecting and testing presentations.",
        {
            "command": {"type": "string"},
            "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 900},
        },
    ),
    _function_tool(
        "view_image",
        "Inspect one rendered slide image at full size using the host Qwen-VL service. "
        "Call this for every final slide, in addition to slides_test.py.",
        {"path": {"type": "string"}, "context": {"type": "string"}},
    ),
    _function_tool(
        "read_skill_resource",
        "Read a text resource from the mounted mature presentation skill.",
        {"path": {"type": "string"}},
    ),
)

CAPABILITY_TOOLS = tuple(
    _function_tool(
        name,
        f"Call the scoped uStudy host capability `{name}`. Arguments are defined by the host.",
        {"arguments": {"type": "object"}},
    )
    for name in HOST_CAPABILITIES
)


class _StreamDeltaEmitter:
    """Coalesce tiny consecutive deltas while preserving timeline boundaries."""

    def __init__(
        self,
        gateway: CapabilityGateway,
        *,
        max_delay_seconds: float = 0.05,
        max_chars: int = 128,
    ) -> None:
        self.gateway = gateway
        self.max_delay_seconds = max_delay_seconds
        self.max_chars = max_chars
        self._event_type: str | None = None
        self._iteration = 0
        self._parts: list[str] = []
        self._chars = 0
        self._started_at = 0.0

    async def push(self, event_type: str, content: str, iteration: int) -> None:
        if self._event_type is not None and (
            self._event_type != event_type or self._iteration != iteration
        ):
            await self.flush()
        if self._event_type is None:
            self._event_type = event_type
            self._iteration = iteration
            self._started_at = time.monotonic()
        self._parts.append(content)
        self._chars += len(content)
        if self._chars >= self.max_chars or time.monotonic() - self._started_at >= self.max_delay_seconds:
            await self.flush()

    async def flush(self) -> None:
        if self._event_type is None:
            return
        content = "".join(self._parts)
        await self.gateway.emit_many(
            [
                (
                    self._event_type,
                    {"content": content, "delta": content, "iteration": self._iteration},
                )
            ]
        )
        self._event_type = None
        self._iteration = 0
        self._parts = []
        self._chars = 0
        self._started_at = 0.0


class PresentationAgentRuntime:
    def __init__(
        self,
        *,
        gateway: CapabilityGateway,
        skill: SkillBundle,
        workspace: str | Path,
        instruction: str,
        sources: list[dict[str, Any]] | None = None,
        max_iterations: int | None = None,  # Accepted only for legacy callers; never enforced.
        command_output_limit: int = 50_000,
    ) -> None:
        self.gateway = gateway
        self.skill = skill
        self.loader = PresentationSkillLoader(skill.root)
        self.workspace = Path(workspace).resolve()
        self.instruction = instruction
        self.sources = sources or []
        self.command_output_limit = command_output_limit
        self.checkpoint_path = self.workspace / ".presentation-agent" / "checkpoint.json"
        self._tool_ledger: dict[str, dict[str, Any]] = {}
        self._pending_tool: dict[str, Any] | None = None
        self._checkpoint_run_id: str | None = None
        self._checkpoint_stage = "initialized"
        self._recovered_interruption: dict[str, Any] | None = None
        self._resume_iteration = 0

    def _system_prompt(self) -> str:
        resources = "\n".join(f"- {name}" for name in self.skill.resources[:500])
        input_files = "\n".join(
            f"- kind={source.get('kind') or 'source'} path={source.get('path')} "
            f"filename={source.get('filename') or Path(str(source.get('path', ''))).name}"
            for source in self.sources
        ) or "- (none)"
        return f"""You are the uStudy teacher presentation agent. Your entire process is running
inside a project-isolated server sandbox. You may execute arbitrary code in this sandbox.
Do not attempt to access the public internet; LLM, image generation, course data and
publishing are available only through the registered host capability tools.
The generate_image host capability is the sandbox equivalent of the presentation
skill's image-generation facility and returns an asset file in this workspace.

The mounted presentation skill is authoritative. Follow it exactly. Do not replace it
with python-pptx or invent a different presentation skill. Build files in /workspace.
The final deck path is /workspace/output/final.pptx. Publishing always requires an
explicit confirmation enforced by the host gateway.

Use write_file/apply_patch for generated .mjs files instead of long shell heredocs. Never
send more than 20000 characters in one write_file call; split large builders into multiple
calls and set append=true after the first chunk.
After rendering, call view_image once for every final slide and fix visual defects before
delivery. view_image attaches the local render to the next turn of this same main-model
conversation; inspect it using the complete agent context. Running slides_test.py alone
does not satisfy visual inspection.

This is a multi-turn workspace. Not every user message requests a build. Greetings,
requirements discovery, outline discussion, and clarification should receive a natural
assistant response and may finish without creating or modifying final.pptx. Only author,
edit, render, or export the deck when the user asks for presentation work in this turn.

SKILL_DIR={self.skill.root}
TMP_DIR=/workspace/tmp
FINAL_PPTX=/workspace/output/final.pptx
RUNTIME_NODE={os.environ.get('RUNTIME_NODE', '')}
RUNTIME_NODE_MODULES={os.environ.get('RUNTIME_NODE_MODULES', '')}
RUNTIME_BIN_DIR={os.environ.get('RUNTIME_BIN_DIR', '')}

Teacher-provided lesson plans and templates downloaded by the capability gateway:
{input_files}

Mounted skill resources (use read_skill_resource or shell tools to inspect as needed):
{resources}

--- BEGIN PRESENTATION SKILL ---
{self.skill.instructions}
--- END PRESENTATION SKILL ---"""

    def _load_messages(self) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": self._system_prompt()}]
        saved_run_id = None
        saved_iteration = 0
        saved_stage = ""
        if self.checkpoint_path.is_file():
            try:
                saved = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
                prior = saved.get("messages", [])
                if isinstance(prior, list):
                    messages.extend(item for item in prior if isinstance(item, dict))
                saved_run_id = str(saved.get("run_id") or "") or None
                saved_iteration = int(saved.get("iteration") or 0)
                saved_stage = str(saved.get("stage") or "")
                ledger = saved.get("tool_ledger")
                if isinstance(ledger, dict):
                    self._tool_ledger = {
                        str(key): value for key, value in ledger.items() if isinstance(value, dict)
                    }
                pending = saved.get("pending_tool")
                if isinstance(pending, dict):
                    self._pending_tool = pending
            except (OSError, ValueError):
                pass
        current_run_id = str(getattr(getattr(self.gateway, "scope", None), "run_id", "local-run"))
        self._checkpoint_run_id = saved_run_id
        if saved_run_id == current_run_id:
            self._resume_iteration = (
                max(saved_iteration - 1, 0)
                if saved_stage == "llm_stream"
                else saved_iteration
            )
        if self._pending_tool:
            call_id = str(self._pending_tool.get("id") or "")
            if call_id and call_id not in self._tool_ledger:
                interrupted = {
                    "ok": False,
                    "error": "interrupted_by_restart",
                    "detail": "The prior sandbox attempt stopped during this tool. Inspect the workspace before deciding whether to retry it.",
                }
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": str(self._pending_tool.get("name") or "tool"),
                        "content": json.dumps(interrupted, ensure_ascii=False),
                    }
                )
                recovered = {
                    "name": str(self._pending_tool.get("name") or "tool"),
                    "arguments": self._pending_tool.get("arguments") or {},
                    "result": interrupted,
                    "status": "error",
                }
                self._tool_ledger[call_id] = recovered
                self._recovered_interruption = {"id": call_id, **recovered}
            self._pending_tool = None
        if saved_run_id != current_run_id:
            self._tool_ledger = {}
            self._recovered_interruption = None
            messages.append({"role": "user", "content": self.instruction})
        return messages

    def _save_checkpoint(self, messages: list[dict[str, Any]], iteration: int) -> None:
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {
            "version": 2,
            "run_id": str(getattr(getattr(self.gateway, "scope", None), "run_id", "local-run")),
            "iteration": iteration,
            "messages": messages[1:],
            "pending_tool": self._pending_tool,
            "tool_ledger": self._tool_ledger,
            "last_sequence": int(getattr(self.gateway, "event_sequence", 0)),
            "deck_state": self._deck_state(),
            "stage": self._checkpoint_stage,
        }
        temporary = self.checkpoint_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(serializable, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.checkpoint_path)

    def _workspace_path(self, raw_path: str, *, must_exist: bool = False) -> Path:
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("workspace path is required")
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = self.workspace / candidate
        candidate = candidate.resolve(strict=False)
        if candidate != self.workspace and self.workspace not in candidate.parents:
            raise ValueError("path must stay inside /workspace")
        if must_exist and not candidate.is_file():
            raise FileNotFoundError(f"workspace file not found: {raw_path}")
        return candidate

    async def _read_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = self._workspace_path(str(arguments.get("path") or ""), must_exist=True)
        content = await asyncio.to_thread(path.read_text, encoding="utf-8")
        offset = max(int(arguments.get("offset") or 0), 0)
        limit = min(max(int(arguments.get("limit") or 100_000), 1), 200_000)
        return {
            "ok": True,
            "path": str(path),
            "content": content[offset : offset + limit],
            "offset": offset,
            "truncated": offset + limit < len(content),
        }

    async def _write_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = self._workspace_path(str(arguments.get("path") or ""))
        content = arguments.get("content")
        if not isinstance(content, str):
            raise TypeError("write_file content must be a string")
        if len(content) > 20_000:
            raise ValueError("write_file content exceeds 20000 characters; split it into chunks")
        path.parent.mkdir(parents=True, exist_ok=True)
        append = bool(arguments.get("append"))
        if append and path.is_file():
            existing = await asyncio.to_thread(path.read_text, encoding="utf-8")
            content = existing + content
        temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
        await asyncio.to_thread(temporary.write_text, content, encoding="utf-8")
        await asyncio.to_thread(temporary.replace, path)
        return {
            "ok": True,
            "path": str(path),
            "bytes": len(content.encode("utf-8")),
            "appended": append,
        }

    async def _apply_patch(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = self._workspace_path(str(arguments.get("path") or ""), must_exist=True)
        hunks = arguments.get("patch")
        if not isinstance(hunks, str) or not hunks.lstrip().startswith("@@"):
            raise ValueError("apply_patch expects unified @@ hunks without file headers")
        relative = path.relative_to(self.workspace).as_posix()
        diff = f"--- a/{relative}\n+++ b/{relative}\n{hunks.rstrip()}\n"
        patch_dir = self.workspace / ".presentation-agent"
        patch_dir.mkdir(parents=True, exist_ok=True)
        descriptor, raw_name = tempfile.mkstemp(prefix="patch-", suffix=".diff", dir=patch_dir)
        os.close(descriptor)
        patch_path = Path(raw_name)
        try:
            patch_path.write_text(diff, encoding="utf-8")
            process = await asyncio.create_subprocess_exec(
                "/usr/bin/patch",
                "--batch",
                "--forward",
                "--reject-file=-",
                "-p1",
                "-i",
                str(patch_path),
                cwd=self.workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
            result = {
                "ok": process.returncode == 0,
                "exit_code": process.returncode,
                "stdout": stdout.decode("utf-8", errors="replace")[: self.command_output_limit],
                "stderr": stderr.decode("utf-8", errors="replace")[: self.command_output_limit],
            }
            if not result["ok"]:
                raise RuntimeError(result["stderr"] or result["stdout"] or "patch failed")
            return result
        finally:
            patch_path.unlink(missing_ok=True)

    async def _execute_command(
        self, arguments: dict[str, Any], *, call_id: str = ""
    ) -> dict[str, Any]:
        command = arguments.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("execute_command requires a non-empty command")
        timeout = min(max(int(arguments.get("timeout_seconds", 600)), 1), 900)
        process = await asyncio.create_subprocess_exec(
            "/bin/bash",
            "-lc",
            command,
            cwd=self.workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        started = time.monotonic()
        communication = asyncio.create_task(process.communicate())
        try:
            while True:
                done, _ = await asyncio.wait({communication}, timeout=10)
                if communication in done:
                    stdout, stderr = communication.result()
                    break
                elapsed = int(time.monotonic() - started)
                if elapsed >= timeout:
                    raise asyncio.TimeoutError
                await self.gateway.emit(
                    "heartbeat",
                    {
                        "stage": "tool_running",
                        "tool_call_id": call_id,
                        "tool": "execute_command",
                        "elapsed_seconds": elapsed,
                    },
                )
        except asyncio.TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), timeout=10)
            except asyncio.TimeoutError:
                pass
            communication.cancel()
            return {"ok": False, "exit_code": None, "error": f"command timed out after {timeout}s"}
        return {
            "ok": process.returncode == 0,
            "exit_code": process.returncode,
            "stdout": stdout.decode("utf-8", errors="replace")[: self.command_output_limit],
            "stderr": stderr.decode("utf-8", errors="replace")[: self.command_output_limit],
        }

    async def _call_tool(
        self, name: str, arguments: dict[str, Any], *, call_id: str = ""
    ) -> dict[str, Any]:
        if name == "load_workspace_dependencies":
            return {
                "runtimeNode": os.environ.get("RUNTIME_NODE", ""),
                "runtimeNodeModules": os.environ.get("RUNTIME_NODE_MODULES", ""),
                "runtimeBinDir": os.environ.get("RUNTIME_BIN_DIR", ""),
                "RUNTIME_NODE": os.environ.get("RUNTIME_NODE", ""),
                "RUNTIME_NODE_MODULES": os.environ.get("RUNTIME_NODE_MODULES", ""),
                "RUNTIME_BIN_DIR": os.environ.get("RUNTIME_BIN_DIR", ""),
            }
        if name == "execute_command":
            return await self._execute_command(arguments, call_id=call_id)
        if name == "read_file":
            return await self._read_file(arguments)
        if name == "write_file":
            return await self._write_file(arguments)
        if name == "apply_patch":
            return await self._apply_patch(arguments)
        if name == "view_image":
            path = self._workspace_path(str(arguments.get("path") or ""), must_exist=True)
            if path.stat().st_size > 8 * 1024 * 1024:
                return {"ok": False, "error": "image exceeds the 8 MiB multimodal limit"}
            return {
                "ok": True,
                "path": str(path),
                "message": "The rendered slide will be attached to the next turn of the same main model.",
            }
        if name == "read_skill_resource":
            content = self.loader.read_resource(str(arguments.get("path", "")))
            return {"content": content}
        if name in HOST_CAPABILITIES:
            if name == "get_class_knowledge_summary" and not any(
                keyword in self.instruction
                for keyword in ("班级", "学情", "薄弱", "掌握", "易错")
            ):
                return {
                    "success": False,
                    "error": "class knowledge summary was not explicitly requested by the teacher",
                }
            nested = arguments.get("arguments")
            tool_arguments = nested if isinstance(nested, dict) else arguments
            result = await self.gateway.call_tool(name, tool_arguments)
            if name in {"generate_image", "view_document_page"} and result.get("success"):
                data = result.get("data") if isinstance(result.get("data"), dict) else {}
                asset_id = str(data.get("asset_id") or result.get("asset_id") or "")
                if asset_id:
                    raw_name = str(data.get("filename") or f"{asset_id}.png")
                    filename = re.sub(
                        r"[^\w.()\-\u4e00-\u9fff ]+",
                        "_",
                        os.path.basename(raw_name.replace("\\", "/")),
                        flags=re.UNICODE,
                    )
                    destination = self.workspace / "assets" / (filename or f"{asset_id}.png")
                    local_path = await self.gateway.download_asset(asset_id, destination)
                    result = _without_image_base64(result)
                    clean_data = result.get("data") if isinstance(result.get("data"), dict) else {}
                    clean_data.update(
                        {
                            "asset_id": asset_id,
                            "local_path": str(local_path),
                            "description": data.get("description", ""),
                        }
                    )
                    result["data"] = clean_data
            return result
        raise ValueError(f"unknown tool: {name}")

    @staticmethod
    def _parse_tool_call(tool_call: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
        function = tool_call.get("function") or tool_call
        name = function.get("name")
        if not isinstance(name, str):
            raise TypeError("tool call has no function name")
        call_id = str(tool_call.get("id") or f"call-{name}")
        raw_arguments = function.get("arguments", {})
        if isinstance(raw_arguments, str):
            arguments = json.loads(raw_arguments or "{}")
        elif isinstance(raw_arguments, dict):
            arguments = raw_arguments
        else:
            raise TypeError("tool arguments must be a JSON object")
        return call_id, name, arguments

    def _deck_state(self) -> tuple[int, int] | None:
        path = self.workspace / "output" / "final.pptx"
        if not path.is_file():
            return None
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns

    def _ensure_workspace_node_modules(self) -> Path:
        """Make bare artifact-tool imports resolve from the skill-mandated TMP_DIR."""

        link = self.workspace / "tmp" / "node_modules"
        target = Path(os.environ.get("RUNTIME_NODE_MODULES", "/opt/runtime/node_modules"))
        if link.is_symlink():
            if link.resolve(strict=False) == target.resolve(strict=False):
                return link
            link.unlink()
        elif link.exists():
            # Preserve user-authored directories; do not replace them recursively.
            return link
        link.symlink_to(target, target_is_directory=True)
        return link

    def _preview_candidates(self) -> list[Path]:
        candidate_groups = [
            list(self.workspace.glob("output/final/slide-*.png")),
            list(self.workspace.glob("output/previews/slide-*.png")),
            list(self.workspace.glob("output/slide-*.png")),
        ]
        temporary_groups: dict[Path, list[Path]] = {}
        for path in self.workspace.glob("tmp/**/slide-*.png"):
            temporary_groups.setdefault(path.parent, []).append(path)
        if temporary_groups:
            newest = max(
                temporary_groups,
                key=lambda directory: max(item.stat().st_mtime_ns for item in temporary_groups[directory]),
            )
            candidate_groups.append(temporary_groups[newest])
        candidates = next((group for group in candidate_groups if group), [])

        def slide_number(path: Path) -> tuple[int, str]:
            match = re.search(r"slide-(\d+)", path.stem)
            return (int(match.group(1)) if match else 10**9, path.name)

        return sorted(set(candidates), key=slide_number)

    def _quality_gaps(self, previews: list[Path]) -> list[str]:
        entries = list(self._tool_ledger.values())
        commands = [
            str((entry.get("arguments") or {}).get("command") or "")
            for entry in entries
            if entry.get("name") == "execute_command"
            and (entry.get("result") or {}).get("ok") is True
        ]
        gaps: list[str] = []
        if not any("mark_artifact_operation_started.mjs" in command for command in commands):
            gaps.append("run mark_artifact_operation_started.mjs exactly once")
        if not previews:
            gaps.append("render every final slide to slide-*.png")
        if not any("slides_test.py" in command for command in commands):
            gaps.append("run slides_test.py and fix all unintended overflow")
        inspected = {
            str(self._workspace_path(str((entry.get("arguments") or {}).get("path") or "")))
            for entry in entries
            if entry.get("name") == "view_image"
            and (entry.get("result") or {}).get("ok", True) is not False
            and (entry.get("arguments") or {}).get("path")
        }
        missing = [str(path) for path in previews if str(path.resolve()) not in inspected]
        if missing:
            gaps.append(f"inspect every rendered slide with view_image; missing {len(missing)}")
        return gaps

    def _semantic_cache_hit(
        self, name: str, arguments: dict[str, Any]
    ) -> tuple[str, dict[str, Any]] | None:
        if name not in SEMANTIC_CACHE_TOOLS:
            return None
        normalized = json.dumps(arguments, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for call_id, entry in reversed(list(self._tool_ledger.items())):
            if (
                entry.get("name") == name
                and entry.get("status") == "done"
                and json.dumps(
                    entry.get("arguments") or {},
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                == normalized
            ):
                return call_id, entry
        return None

    def _tool_context_content(self, result: dict[str, Any]) -> str:
        raw = json.dumps(result, ensure_ascii=False)
        limit = 24_000
        if len(raw) <= limit:
            return raw
        return raw[:limit] + json.dumps(
            {"truncated": True, "original_chars": len(raw)}, ensure_ascii=False
        )

    def _image_followup_message(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        path = self._workspace_path(str(arguments.get("path") or ""), must_exist=True)
        raw = path.read_bytes()
        if raw[:8] == b"\x89PNG\r\n\x1a\n":
            mime_type = "image/png"
        elif raw[:2] == b"\xff\xd8":
            mime_type = "image/jpeg"
        elif raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
            mime_type = "image/webp"
        else:
            raise ValueError("view_image only supports PNG, JPEG or WebP")
        context = str(arguments.get("context") or "rendered presentation slide")
        return {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Inspect this rendered slide at full size using the complete presentation "
                        f"context. Context: {context}. Report concrete clipping, overlap, wrapping, "
                        "legibility, crop, hierarchy or consistency defects, then fix the deck when needed."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{base64.b64encode(raw).decode('ascii')}"
                    },
                },
            ],
        }

    @staticmethod
    def _compact_consumed_images(messages: list[dict[str, Any]]) -> None:
        for message in messages:
            content = message.get("content")
            if message.get("role") != "user" or not isinstance(content, list):
                continue
            if any(
                isinstance(part, dict) and part.get("type") == "image_url"
                for part in content
            ):
                message["content"] = (
                    "[A rendered slide image was inspected by the main model in the immediately following turn.]"
                )

    async def run(self) -> Path | None:
        self.workspace.mkdir(parents=True, exist_ok=True)
        (self.workspace / "tmp").mkdir(exist_ok=True)
        (self.workspace / "output").mkdir(exist_ok=True)
        (self.workspace / "assets").mkdir(exist_ok=True)
        (self.workspace / ".home").mkdir(exist_ok=True)
        (self.workspace / ".tmp").mkdir(exist_ok=True)
        self._ensure_workspace_node_modules()
        messages = self._load_messages()
        tools = [*LOCAL_TOOLS, *CAPABILITY_TOOLS]
        # A same-run checkpoint owns unfinished artifacts, including a deck that
        # was exported before interruption but has not yet been delivered.
        current_run_id = str(getattr(getattr(self.gateway, "scope", None), "run_id", "local-run"))
        initial_deck_state = (
            None if self._checkpoint_run_id == current_run_id else self._deck_state()
        )
        self._checkpoint_stage = "starting"
        self._save_checkpoint(messages, self._resume_iteration)
        await self.gateway.emit(
            "run_started",
            {
                "skill_root": str(self.skill.root),
                "attempt": int(os.environ.get("PRESENTATION_ATTEMPT", "1")),
                "resume_iteration": self._resume_iteration,
            },
        )
        if self._recovered_interruption:
            recovered = self._recovered_interruption
            await self.gateway.emit(
                "tool_call",
                {
                    "id": recovered["id"],
                    "name": recovered["name"],
                    "tool": recovered["name"],
                    "status": "error",
                    "arguments": recovered["arguments"],
                    "result": recovered["result"],
                    "error": "interrupted_by_restart",
                    "iteration": 0,
                },
            )
        for iteration in count(self._resume_iteration + 1):
            self._checkpoint_stage = "llm_stream"
            self._save_checkpoint(messages, iteration)
            content_parts: list[str] = []
            tool_calls: list[dict[str, Any]] = []
            delta_emitter = _StreamDeltaEmitter(self.gateway)
            async for event in self.gateway.stream_complete(
                messages, tools, enable_thinking=True
            ):
                event_type = event.get("type")
                if event_type == "thinking":
                    delta = str(event.get("content") or "")
                    if delta:
                        await delta_emitter.push("thinking_delta", delta, iteration)
                elif event_type == "content":
                    delta = str(event.get("content") or "")
                    if delta:
                        content_parts.append(delta)
                        await delta_emitter.push("text_delta", delta, iteration)
                elif event_type == "tool_call_start":
                    await delta_emitter.flush()
                    await self.gateway.emit(
                        "tool_call",
                        {
                            "id": str(event.get("id") or ""),
                            "name": str(event.get("name") or ""),
                            "tool": str(event.get("name") or ""),
                            "status": "running",
                            "iteration": iteration,
                        },
                    )
                elif event_type == "tool_call_end":
                    tool_calls.append(
                        {
                            "id": str(event.get("id") or ""),
                            "type": "function",
                            "function": {
                                "name": str(event.get("name") or ""),
                                "arguments": json.dumps(
                                    event.get("arguments") or {}, ensure_ascii=False
                                ),
                            },
                        }
                    )
                elif event_type == "done":
                    await delta_emitter.flush()
                elif event_type == "error":
                    await delta_emitter.flush()
                    raise AgentStreamError(
                        str(event.get("message") or "LLM stream failed"),
                        retryable=event.get("retryable") is not False,
                        status_code=event.get("status_code"),
                        provider_code=event.get("provider_code"),
                        error_type=event.get("error_type"),
                    )
            await delta_emitter.flush()
            content = "".join(content_parts)
            self._compact_consumed_images(messages)
            assistant_message: dict[str, Any] = {"role": "assistant", "content": content or ""}
            if tool_calls:
                assistant_message["tool_calls"] = tool_calls
            messages.append(assistant_message)
            self._checkpoint_stage = "assistant_received"
            self._save_checkpoint(messages, iteration)
            if not tool_calls:
                final_path = self.workspace / "output" / "final.pptx"
                current_deck_state = self._deck_state()
                if (
                    current_deck_state is None
                    or current_deck_state[0] == 0
                    or current_deck_state == initial_deck_state
                ):
                    await self.gateway.emit(
                        "conversation_complete",
                        {
                            "message": content or "可以继续告诉我你希望怎样制作或修改课件。",
                            "artifact_ready": False,
                        },
                    )
                    return None
                preview_candidates = self._preview_candidates()
                quality_gaps = self._quality_gaps(preview_candidates)
                if quality_gaps:
                    messages.append(
                        {
                            "role": "user",
                            "content": "The deck exists but the authoritative Presentations skill QA is incomplete. "
                            + "; ".join(quality_gaps)
                            + ". Continue working and do not claim completion yet.",
                        }
                    )
                    self._checkpoint_stage = "qa_required"
                    self._save_checkpoint(messages, iteration)
                    await self.gateway.emit(
                        "checkpoint",
                        {"iteration": iteration, "stage": "qa_required", "gaps": quality_gaps},
                    )
                    continue
                self._checkpoint_stage = "artifact_upload"
                self._save_checkpoint(messages, iteration)
                artifact = await self.gateway.upload_artifact(
                    kind="pptx",
                    file_path=final_path,
                    filename="final.pptx",
                    metadata={"iteration": iteration},
                )
                previews: list[dict[str, Any]] = []
                for index, preview_path in enumerate(preview_candidates, start=1):
                    try:
                        uploaded = await self.gateway.upload_artifact(
                            kind="preview",
                            file_path=preview_path,
                            filename=preview_path.name,
                            metadata={"page": index},
                        )
                        previews.append(uploaded)
                    except Exception as exc:  # noqa: BLE001 - preview failures are non-fatal
                        await self.gateway.emit(
                            "warning",
                            {"message": "preview upload failed", "file": preview_path.name, "error": str(exc)},
                        )
                if not preview_candidates:
                    await self.gateway.emit(
                        "warning", {"message": "no rendered slide previews were found to upload"}
                    )
                await self.gateway.emit(
                    "presentation_ready",
                    {
                        "artifact": artifact,
                        "previews": previews,
                        "size": final_path.stat().st_size,
                        "message": content or "PPT 已生成完成",
                    },
                )
                return final_path
            image_followups: list[dict[str, Any]] = []
            for raw_call in tool_calls:
                call_id, name, arguments = self._parse_tool_call(raw_call)
                cached = self._tool_ledger.get(call_id)
                if cached:
                    result = cached.get("result") or {}
                    status = str(cached.get("status") or "done")
                else:
                    semantic_hit = self._semantic_cache_hit(name, arguments)
                    if semantic_hit:
                        cached_id, _cached_entry = semantic_hit
                        result = {
                            "ok": True,
                            "cached": True,
                            "same_as_tool_call_id": cached_id,
                            "message": "Identical read-only tool result is already present earlier in the context.",
                        }
                        status = "done"
                        self._tool_ledger[call_id] = {
                            "name": name,
                            "arguments": arguments,
                            "result": result,
                            "status": status,
                        }
                    else:
                        self._pending_tool = {
                            "id": call_id,
                            "name": name,
                            "arguments": arguments,
                            "iteration": iteration,
                            "started_at": time.time(),
                        }
                        self._checkpoint_stage = "tool_running"
                        self._save_checkpoint(messages, iteration)
                        try:
                            result = await self._call_tool(name, arguments, call_id=call_id)
                            # A publish request intentionally returns
                            # ``requires_confirmation`` until the teacher
                            # confirms it in the UI. That is a completed tool
                            # call, not an execution failure.
                            status = (
                                "done"
                                if result.get("ok", True) is not False
                                or result.get("requires_confirmation") is True
                                else "error"
                            )
                        except Exception as exc:  # noqa: BLE001 - tool errors go to LLM for recovery
                            detail = str(exc).strip() or exc.__class__.__name__
                            result = {
                                "ok": False,
                                "error": detail,
                                "error_type": exc.__class__.__name__,
                            }
                            status = "error"
                        self._tool_ledger[call_id] = {
                            "name": name,
                            "arguments": arguments,
                            "result": result,
                            "status": status,
                        }
                        self._pending_tool = None
                await self.gateway.emit(
                    "tool_call",
                    {
                        "id": call_id,
                        "name": name,
                        "tool": name,
                        "status": status,
                        "arguments": arguments,
                        "result": result,
                        "iteration": iteration,
                    },
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": name,
                        "content": self._tool_context_content(result),
                    }
                )
                if name == "view_image" and result.get("ok") is True and not result.get("cached"):
                    image_followups.append(self._image_followup_message(arguments))
                self._checkpoint_stage = "tool_completed"
                self._save_checkpoint(messages, iteration)
            messages.extend(image_followups)
            self._save_checkpoint(messages, iteration)
            await self.gateway.emit("checkpoint", {"iteration": iteration})


def _without_image_base64(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_image_base64(item)
            for key, item in value.items()
            if key != "image_base64"
        }
    if isinstance(value, list):
        return [_without_image_base64(item) for item in value]
    return value
