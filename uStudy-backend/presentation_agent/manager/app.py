"""Internal HTTP control plane for presentation-agent containers."""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, status

from presentation_agent.manager.docker_cli import (
    DockerCLI,
    DockerCommandError,
    DockerUnavailable,
)
from presentation_agent.models import (
    RunCreated,
    RunCreateRequest,
    RunStatus,
    validate_identifier,
)

STATE_DIR = Path(os.environ.get("PRESENTATION_MANAGER_STATE_DIR", "/var/lib/presentation-manager"))
MANAGER_TOKEN = os.environ.get("PRESENTATION_SANDBOX_MANAGER_TOKEN", "")
docker = DockerCLI()
manager_lock = asyncio.Lock()


def _cancel_marker(run_id: str) -> Path:
    validate_identifier(run_id)
    return STATE_DIR / "cancelled" / run_id


def _run_state_path(run_id: str) -> Path:
    validate_identifier(run_id)
    return STATE_DIR / "runs" / f"{run_id}.json"


def _load_run_state(run_id: str) -> dict | None:
    path = _run_state_path(run_id)
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _save_run_state(state: dict) -> None:
    path = _run_state_path(str(state["request"]["run_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def _new_run_state(request: RunCreateRequest) -> dict:
    now = time.time()
    return {
        "request": request.model_dump(mode="json"),
        "attempt": 1,
        "created_at": now,
        "next_retry_at": None,
    }


def _request_for_attempt(state: dict, attempt: int) -> RunCreateRequest:
    request = RunCreateRequest.model_validate(state["request"])
    return request.model_copy(update={"attempt": attempt})


def _retry_delay(state: dict) -> int:
    request = RunCreateRequest.model_validate(state["request"])
    index = min(max(int(state.get("attempt", 1)) - 1, 0), len(request.retry_backoff_seconds) - 1)
    return request.retry_backoff_seconds[index]


def _is_retryable(state: dict, status_value: RunStatus, now: float) -> bool:
    request = RunCreateRequest.model_validate(state["request"])
    return (
        status_value.status == "failed"
        and status_value.exit_code not in {78, 124}
        and int(state.get("attempt", 1)) < request.max_attempts
        and not _cancel_marker(request.run_id).exists()
    )


def _remove_if_present(run_id: str) -> None:
    try:
        docker.remove_run(run_id)
    except DockerCommandError as exc:
        if "No such container" not in str(exc):
            raise


def _reconcile_retries(now: float) -> None:
    run_dir = STATE_DIR / "runs"
    if not run_dir.is_dir():
        return
    for path in run_dir.glob("*.json"):
        state = _load_run_state(path.stem)
        if not state:
            continue
        try:
            request = RunCreateRequest.model_validate(state["request"])
        except (KeyError, TypeError, ValueError):
            continue
        try:
            current = docker.inspect_run(request.run_id)
        except DockerCommandError:
            continue
        if current.status in {"succeeded", "cancelled"}:
            path.unlink(missing_ok=True)
            continue
        if not _is_retryable(state, current, now):
            if current.status == "failed":
                path.unlink(missing_ok=True)
            continue
        retry_at = state.get("next_retry_at")
        if retry_at is None:
            state["next_retry_at"] = now + _retry_delay(state)
            _save_run_state(state)
            continue
        if now < float(retry_at):
            continue
        next_attempt = int(state.get("attempt", 1)) + 1
        _remove_if_present(request.run_id)
        docker.create_run(_request_for_attempt(state, next_attempt))
        state["attempt"] = next_attempt
        state["next_retry_at"] = None
        _save_run_state(state)


async def require_manager_token(authorization: str | None = Header(default=None)) -> None:
    if not MANAGER_TOKEN:
        raise HTTPException(status_code=503, detail="sandbox manager token is not configured")
    expected = f"Bearer {MANAGER_TOKEN}"
    if authorization is None or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid manager token")


def _translate_docker_error(exc: Exception) -> HTTPException:
    if isinstance(exc, DockerUnavailable):
        return HTTPException(status_code=503, detail=str(exc))
    message = str(exc)
    if "No such container" in message:
        return HTTPException(status_code=404, detail="presentation run not found")
    if "Conflict" in message and "already in use" in message:
        return HTTPException(status_code=409, detail="presentation run already exists")
    return HTTPException(status_code=502, detail=f"Docker operation failed: {message}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    stop = asyncio.Event()

    async def enforce_deadlines() -> None:
        last_limit_check = 0.0
        while not stop.is_set():
            try:
                now = time.time()
                async with manager_lock:
                    await asyncio.to_thread(_reconcile_retries, now)
                    if now - last_limit_check >= 30:
                        await asyncio.to_thread(docker.stop_expired_runs, int(now))
                        last_limit_check = now
            except (ValueError, DockerUnavailable, DockerCommandError):
                pass
            try:
                await asyncio.wait_for(stop.wait(), timeout=2)
            except asyncio.TimeoutError:
                pass

    watcher = asyncio.create_task(enforce_deadlines())
    try:
        yield
    finally:
        stop.set()
        await watcher


app = FastAPI(title="uStudy Presentation Sandbox Manager", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    try:
        await asyncio.to_thread(docker.ping)
    except (DockerUnavailable, DockerCommandError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "ok"}


@app.post("/runs", response_model=RunCreated, dependencies=[Depends(require_manager_token)])
async def create_run(request: RunCreateRequest) -> RunCreated:
    try:
        request = request.model_copy(update={"attempt": 1})
        state = _new_run_state(request)
        async with manager_lock:
            created = await asyncio.to_thread(docker.create_run, request)
            await asyncio.to_thread(_save_run_state, state)
            marker = _cancel_marker(request.run_id)
            marker.unlink(missing_ok=True)
        return created
    except (ValueError, DockerUnavailable, DockerCommandError) as exc:
        raise _translate_docker_error(exc) from exc


@app.get(
    "/runs/{run_id}", response_model=RunStatus, dependencies=[Depends(require_manager_token)]
)
async def get_run(run_id: str) -> RunStatus:
    try:
        validate_identifier(run_id)
        cancelled = _cancel_marker(run_id).exists()
        current = await asyncio.to_thread(docker.inspect_run, run_id, cancelled=cancelled)
        state = _load_run_state(run_id)
        if state:
            current.attempt = int(state.get("attempt", current.attempt))
            request = RunCreateRequest.model_validate(state["request"])
            current.max_attempts = request.max_attempts
            if _is_retryable(state, current, time.time()):
                current.status = "recovering"
                retry_at = state.get("next_retry_at")
                current.retry_at = str(retry_at) if retry_at is not None else None
        return current
    except (ValueError, DockerUnavailable, DockerCommandError) as exc:
        raise _translate_docker_error(exc) from exc


@app.post(
    "/runs/{run_id}/cancel",
    response_model=RunStatus,
    dependencies=[Depends(require_manager_token)],
)
async def cancel_run(run_id: str) -> RunStatus:
    try:
        validate_identifier(run_id)
        marker = _cancel_marker(run_id)
        async with manager_lock:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch(exist_ok=True)
            await asyncio.to_thread(docker.cancel_run, run_id)
            return await asyncio.to_thread(docker.inspect_run, run_id, cancelled=True)
    except (ValueError, DockerUnavailable, DockerCommandError) as exc:
        raise _translate_docker_error(exc) from exc


@app.post(
    "/runs/{run_id}/resume",
    response_model=RunCreated,
    dependencies=[Depends(require_manager_token)],
)
async def resume_run(run_id: str, request: RunCreateRequest) -> RunCreated:
    """Reset the retry budget while preserving the project workspace volume."""

    try:
        validate_identifier(run_id)
        if request.run_id != run_id:
            raise ValueError("run id does not match resume payload")
        request = request.model_copy(update={"attempt": 1})
        state = _new_run_state(request)
        async with manager_lock:
            await asyncio.to_thread(_remove_if_present, run_id)
            created = await asyncio.to_thread(docker.create_run, request)
            await asyncio.to_thread(_save_run_state, state)
            _cancel_marker(run_id).unlink(missing_ok=True)
        return created
    except (ValueError, DockerUnavailable, DockerCommandError) as exc:
        raise _translate_docker_error(exc) from exc
