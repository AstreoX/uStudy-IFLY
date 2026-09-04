"""Persistence, sandbox orchestration and capability implementations."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import shutil
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import aiofiles
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from chat.tools.image_tools import ImageToolExecutor
from chat.tools.rag_tools import RAGToolExecutor
from config import get_settings
from db.models import (
    Conversation,
    ConversationKind,
    DocumentType,
    Edge,
    EdgeType,
    Message,
    MessageResponseStatus,
    MessageRole,
    Node,
    PresentationAssetKind,
    PresentationRevisionStatus,
    PresentationRunStatus,
    SpaceDocument,
    SpaceMember,
    SpaceMemberRole,
    TeacherPresentationAsset,
    TeacherPresentationEvent,
    TeacherPresentationProject,
    TeacherPresentationPublication,
    TeacherPresentationRevision,
    TeacherPresentationRun,
)
from documents.service import schedule_document_processing
from teacher.presentations.manager import SandboxManagerClient, SandboxManagerError
from teacher.service import TeacherAnalyticsService

ACTIVE_RUN_STATUSES = {
    PresentationRunStatus.QUEUED,
    PresentationRunStatus.RUNNING,
    PresentationRunStatus.RECOVERING,
    PresentationRunStatus.WAITING_CONFIRMATION,
}
TERMINAL_RUN_STATUSES = {
    PresentationRunStatus.COMPLETED,
    PresentationRunStatus.FAILED,
    PresentationRunStatus.CANCELLED,
}
MAX_SOURCE_BYTES = 50 * 1024 * 1024
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
SOURCE_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def private_root() -> Path:
    settings = get_settings()
    configured = getattr(settings, "presentation_private_dir", None) or os.getenv(
        "PRESENTATION_PRIVATE_DIR"
    )
    root = Path(configured) if configured else Path(settings.upload_dir).resolve().parent / "private-presentations"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def resolve_private_path(value: str | Path, *, must_exist: bool = True) -> Path:
    path = Path(value).resolve()
    root = private_root()
    if path != root and root not in path.parents:
        raise HTTPException(status_code=400, detail="非法的私有文件路径")
    if must_exist and not path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return path


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def get_owned_project(
    db: AsyncSession, project_id: UUID, user_id: UUID, space_id: UUID | None = None
) -> TeacherPresentationProject:
    stmt = select(TeacherPresentationProject).where(
        TeacherPresentationProject.id == project_id,
        TeacherPresentationProject.teacher_user_id == user_id,
    )
    if space_id is not None:
        stmt = stmt.where(TeacherPresentationProject.space_id == space_id)
    project = await db.scalar(stmt)
    if project is None:
        raise HTTPException(status_code=404, detail="PPT 项目不存在")
    return project


async def create_project(
    db: AsyncSession, *, space_id: UUID, user_id: UUID, title: str
) -> TeacherPresentationProject:
    conversation = Conversation(
        user_id=user_id,
        space_id=space_id,
        title=title.strip(),
        kind=ConversationKind.TEACHER_PRESENTATION,
    )
    db.add(conversation)
    await db.flush()
    project = TeacherPresentationProject(
        space_id=space_id,
        teacher_user_id=user_id,
        conversation_id=conversation.id,
        title=title.strip(),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def list_projects(db: AsyncSession, *, space_id: UUID, user_id: UUID) -> list[TeacherPresentationProject]:
    return list(
        (
            await db.scalars(
                select(TeacherPresentationProject)
                .where(
                    TeacherPresentationProject.space_id == space_id,
                    TeacherPresentationProject.teacher_user_id == user_id,
                )
                .order_by(TeacherPresentationProject.updated_at.desc())
            )
        ).all()
    )


async def save_source(
    db: AsyncSession,
    *,
    project: TeacherPresentationProject,
    upload: UploadFile,
    kind: PresentationAssetKind,
) -> TeacherPresentationAsset:
    filename = Path(upload.filename or "source.bin").name
    suffix = Path(filename).suffix.lower()
    if kind == PresentationAssetKind.TEMPLATE and suffix != ".pptx":
        raise HTTPException(status_code=400, detail="PPT 模板必须是 .pptx 文件")
    if kind == PresentationAssetKind.SOURCE and suffix not in SOURCE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="教案仅支持 PDF、DOCX、TXT 或 Markdown")
    destination_dir = private_root() / str(project.id) / "sources"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{uuid4().hex}-{filename}"
    size = 0
    try:
        async with aiofiles.open(destination, "wb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_SOURCE_BYTES:
                    raise HTTPException(status_code=413, detail="单个教案或模板最大 50 MB")
                await output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    asset = TeacherPresentationAsset(
        project_id=project.id,
        kind=kind,
        filename=filename,
        private_path=str(destination),
        mime_type=upload.content_type or mimetypes.guess_type(filename)[0],
        file_size=size,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


async def _next_revision_number(db: AsyncSession, project_id: UUID) -> int:
    value = await db.scalar(
        select(func.max(TeacherPresentationRevision.revision_number)).where(
            TeacherPresentationRevision.project_id == project_id
        )
    )
    return int(value or 0) + 1


async def create_run(
    db: AsyncSession,
    *,
    project: TeacherPresentationProject,
    content: str,
    gateway_url: str,
    source_ids: list[UUID] | None = None,
    expected_revision_id: UUID | None = None,
    manager: SandboxManagerClient | None = None,
) -> tuple[TeacherPresentationRun, str]:
    locked_project = await db.scalar(
        select(TeacherPresentationProject)
        .where(TeacherPresentationProject.id == project.id)
        .with_for_update()
    )
    if locked_project is None:
        raise HTTPException(status_code=404, detail="PPT 项目不存在")
    project = locked_project
    if expected_revision_id != project.current_revision_id:
        raise HTTPException(status_code=409, detail="PPT 项目版本已变化，请刷新后重试")
    selected_source_ids = list(dict.fromkeys(source_ids or []))
    if not selected_source_ids and project.current_revision_id:
        current_revision = await db.get(
            TeacherPresentationRevision, project.current_revision_id
        )
        if current_revision:
            selected_source_ids = [
                UUID(item)
                for item in (current_revision.manifest or {}).get("source_ids", [])
            ]
    if selected_source_ids:
        valid_ids = set(
            (
                await db.scalars(
                    select(TeacherPresentationAsset.id).where(
                        TeacherPresentationAsset.project_id == project.id,
                        TeacherPresentationAsset.id.in_(selected_source_ids),
                        TeacherPresentationAsset.kind.in_(
                            [PresentationAssetKind.SOURCE, PresentationAssetKind.TEMPLATE]
                        ),
                    )
                )
            ).all()
        )
        if valid_ids != set(selected_source_ids):
            raise HTTPException(status_code=422, detail="source_ids 包含无效或不属于项目的附件")
    active = await db.scalar(
        select(TeacherPresentationRun.id).where(
            TeacherPresentationRun.project_id == project.id,
            TeacherPresentationRun.status.in_(ACTIVE_RUN_STATUSES),
        )
    )
    if active:
        raise HTTPException(status_code=409, detail="该项目已有正在执行的 PPT Agent")

    token = secrets.token_urlsafe(48)
    revision = TeacherPresentationRevision(
        project_id=project.id,
        parent_revision_id=project.current_revision_id,
        revision_number=await _next_revision_number(db, project.id),
        status=PresentationRevisionStatus.DRAFT,
        prompt=content,
        manifest={"source_ids": [str(item) for item in selected_source_ids]},
    )
    db.add(revision)
    await db.flush()
    run = TeacherPresentationRun(
        project_id=project.id,
        revision_id=revision.id,
        user_id=project.teacher_user_id,
        space_id=project.space_id,
        status=PresentationRunStatus.QUEUED,
        capability_token_hash=_token_hash(token),
        capability_expires_at=utcnow() + timedelta(hours=6),
        prompt=content,
        attempt_count=1,
        retry_deadline_at=utcnow() + timedelta(minutes=30),
    )
    db.add(run)
    db.add(Message(conversation_id=project.conversation_id, role=MessageRole.USER, content=content))
    await db.flush()
    db.add(
        TeacherPresentationEvent(
            run_id=run.id,
            sequence=1,
            event_type="presentation_progress",
            payload={"stage": "queued", "progress": 0, "run_id": str(run.id)},
        )
    )
    await db.commit()

    asset_stmt = (
        select(TeacherPresentationAsset)
        .where(
            TeacherPresentationAsset.project_id == project.id,
            TeacherPresentationAsset.kind.in_(
                [PresentationAssetKind.SOURCE, PresentationAssetKind.TEMPLATE]
            ),
        )
        .order_by(TeacherPresentationAsset.created_at)
    )
    asset_stmt = asset_stmt.where(TeacherPresentationAsset.id.in_(selected_source_ids))
    assets = list(
        (
            await db.scalars(asset_stmt)
        ).all()
    )
    run_gateway_url = f"{gateway_url.rstrip('/')}/{run.id}"
    payload = {
        "run_id": str(run.id),
        "project_id": str(project.id),
        "revision_id": str(revision.id),
        "space_id": str(project.space_id),
        "user_id": str(project.teacher_user_id),
        "instruction": content,
        "gateway_url": run_gateway_url,
        "capability_token": token,
        "max_iterations": 60,
        "max_seconds": 1800,
        "max_attempts": 5,
        "retry_backoff_seconds": [2, 5, 10, 20, 30],
        "metadata": {
            "revision_id": str(revision.id),
            "parent_revision_id": str(project.current_revision_id) if project.current_revision_id else None,
            "source_ids": [str(asset.id) for asset in assets],
        },
    }
    manager = manager or SandboxManagerClient()
    try:
        manager_data = await manager.create_run(payload)
    except Exception as exc:
        detail = str(exc).strip() or exc.__class__.__name__
        # Configuration and manager availability failures cannot be fixed by
        # replaying the same checkpoint. Persist this hint so the UI does not
        # offer a misleading "continue task" action.
        retryable = not (
            "未配置" in detail
            or "not configured" in detail.lower()
            or "Docker CLI is unavailable" in detail
            or "PRESENTATION_SKILL_HOST_DIR" in detail
        )
        await append_event(
            db,
            run=run,
            project=project,
            sequence=2,
            event_type="error",
            payload={
                "message": "PPT Agent 沙盒启动失败",
                "detail": detail,
                "error_type": exc.__class__.__name__,
                "stage": "manager_create",
                "retryable": retryable,
            },
        )
        response_status = 503 if "未配置" in detail or "(503)" in detail else 502
        raise HTTPException(status_code=response_status, detail="PPT Agent 沙盒启动失败") from exc

    run.manager_run_id = str(manager_data.get("run_id") or manager_data["id"])
    manager_status = str(manager_data.get("status", "queued"))
    if manager_status == "starting":
        manager_status = "running"
    if manager_status in {item.value for item in PresentationRunStatus}:
        run.status = PresentationRunStatus(manager_status)
    await db.commit()
    await db.refresh(run)
    return run, token


async def delete_source(
    db: AsyncSession,
    *,
    project: TeacherPresentationProject,
    asset_id: UUID,
) -> None:
    asset = await db.scalar(
        select(TeacherPresentationAsset).where(
            TeacherPresentationAsset.id == asset_id,
            TeacherPresentationAsset.project_id == project.id,
            TeacherPresentationAsset.kind.in_(
                [PresentationAssetKind.SOURCE, PresentationAssetKind.TEMPLATE]
            ),
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="附件不存在")
    revisions = list(
        (
            await db.scalars(
                select(TeacherPresentationRevision.manifest).where(
                    TeacherPresentationRevision.project_id == project.id,
                    TeacherPresentationRevision.status == PresentationRevisionStatus.COMPLETED,
                )
            )
        ).all()
    )
    if any(str(asset.id) in (manifest or {}).get("source_ids", []) for manifest in revisions):
        raise HTTPException(status_code=409, detail="附件已被完成版本引用，不能删除")
    path = resolve_private_path(asset.private_path, must_exist=False)
    await db.delete(asset)
    await db.commit()
    with suppress(OSError):
        path.unlink(missing_ok=True)


async def verify_capability(
    db: AsyncSession,
    *,
    run_id: UUID,
    token: str,
    header_run_id: str | None,
    header_project_id: str | None,
) -> tuple[TeacherPresentationRun, TeacherPresentationProject]:
    run = await db.get(TeacherPresentationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run 不存在")
    project = await db.get(TeacherPresentationProject, run.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project 不存在")
    if not token or not hmac.compare_digest(run.capability_token_hash, _token_hash(token)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效 capability token")
    if _as_aware(run.capability_expires_at) <= utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="capability token 已过期")
    if header_run_id != str(run.id) or header_project_id != str(project.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="capability scope 不匹配")
    # Revalidate every identity/scope relation from the database, never from sandbox input.
    if (
        project.id != run.project_id
        or project.teacher_user_id != run.user_id
        or project.space_id != run.space_id
        or project.conversation_id is None
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="run scope 已失效")
    role = await db.scalar(
        select(SpaceMember.role).where(
            SpaceMember.space_id == run.space_id,
            SpaceMember.user_id == run.user_id,
        )
    )
    if role != SpaceMemberRole.TEACHER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="教师权限已失效")
    return run, project


async def _persist_terminal_assistant(
    db: AsyncSession,
    *,
    run: TeacherPresentationRun,
    project: TeacherPresentationProject,
    fallback_text: str,
    response_status: MessageResponseStatus = MessageResponseStatus.COMPLETED,
    fallback_tool_calls: list[dict[str, Any]] | None = None,
) -> None:
    existing_messages = list(
        (
            await db.scalars(
                select(Message).where(
                    Message.conversation_id == project.conversation_id,
                    Message.role == MessageRole.ASSISTANT,
                )
            )
        ).all()
    )
    existing = next(
        (
            message
            for message in existing_messages
            if str((message.llm_context or {}).get("run_id") or "") == str(run.id)
        ),
        None,
    )
    assistant_text, llm_context, tool_calls = await build_run_message_trace(
        db, run.id, fallback_text
    )
    if existing is not None:
        existing.content = assistant_text
        existing.llm_context = llm_context
        existing.tool_calls = tool_calls or fallback_tool_calls
        existing.response_status = response_status
        return
    db.add(
        Message(
            conversation_id=project.conversation_id,
            role=MessageRole.ASSISTANT,
            content=assistant_text,
            llm_context=llm_context,
            tool_calls=tool_calls or fallback_tool_calls,
            response_status=response_status,
        )
    )


async def append_event(
    db: AsyncSession,
    *,
    run: TeacherPresentationRun,
    project: TeacherPresentationProject,
    sequence: int | None,
    event_type: str,
    payload: dict[str, Any],
    commit: bool = True,
) -> TeacherPresentationEvent:
    if sequence is None:
        # Event producers are single-writer per run. Locking the run serializes
        # retries/reconnects before allocating the next persisted SSE cursor.
        await db.scalar(
            select(TeacherPresentationRun.id)
            .where(TeacherPresentationRun.id == run.id)
            .with_for_update()
        )
        maximum = await db.scalar(
            select(func.max(TeacherPresentationEvent.sequence)).where(
                TeacherPresentationEvent.run_id == run.id
            )
        )
        sequence = int(maximum or 0) + 1
    existing = await db.scalar(
        select(TeacherPresentationEvent).where(
            TeacherPresentationEvent.run_id == run.id,
            TeacherPresentationEvent.sequence == sequence,
        )
    )
    if existing:
        if existing.event_type != event_type or existing.payload != payload:
            raise HTTPException(status_code=409, detail="事件 sequence 已被不同内容占用")
        return existing

    event = TeacherPresentationEvent(
        run_id=run.id, sequence=sequence, event_type=event_type, payload=payload
    )
    db.add(event)
    revision = await db.get(TeacherPresentationRevision, run.revision_id)
    if event_type in {
        "run_started",
        "presentation_progress",
        "thinking_delta",
        "text_delta",
        "tool_call",
    }:
        if run.status in {PresentationRunStatus.QUEUED, PresentationRunStatus.RECOVERING}:
            run.status = PresentationRunStatus.RUNNING
            run.started_at = run.started_at or utcnow()
        if event_type == "run_started":
            run.attempt_count = max(
                run.attempt_count, int(payload.get("attempt") or run.attempt_count)
            )
    elif event_type == "heartbeat":
        run.last_heartbeat_at = utcnow()
        if run.status in {PresentationRunStatus.QUEUED, PresentationRunStatus.RECOVERING}:
            run.status = PresentationRunStatus.RUNNING
    elif event_type == "attempt_failed":
        run.status = PresentationRunStatus.RECOVERING
        run.error_message = str(payload.get("detail") or payload.get("message") or "") or None
        run.attempt_count = max(
            run.attempt_count, int(payload.get("attempt") or run.attempt_count)
        )
        run.completed_at = None
        revision.status = PresentationRevisionStatus.DRAFT
        revision.error_message = None
    elif event_type == "publish_confirmation_required":
        run.status = PresentationRunStatus.WAITING_CONFIRMATION
    elif event_type == "conversation_complete":
        run.status = PresentationRunStatus.COMPLETED
        run.completed_at = utcnow()
        project.updated_at = utcnow()
        payload.setdefault("run_id", str(run.id))
        payload.setdefault("artifact_ready", False)
        event.payload = dict(payload)
        # The trace query below must see the enriched terminal event and cursor.
        await db.flush()
        fallback_text = str(
            payload.get("message")
            or "可以继续告诉我你希望怎样制作或修改课件。"
        )
        await _persist_terminal_assistant(
            db,
            run=run,
            project=project,
            fallback_text=fallback_text,
        )
    elif event_type == "presentation_ready":
        if payload.get("pptx_base64") or payload.get("pptx_path"):
            await _materialize_ready_payload(db, project, revision, payload)
        elif revision.pptx_path:
            revision.status = PresentationRevisionStatus.COMPLETED
            revision.summary = str(payload.get("summary") or "") or revision.summary
            revision.manifest = payload.get("manifest") or revision.manifest or {}
            revision.completed_at = utcnow()
        else:
            raise HTTPException(status_code=422, detail="presentation_ready 前尚未上传 PPTX 产物")
        run.status = PresentationRunStatus.COMPLETED
        run.completed_at = utcnow()
        project.current_revision_id = revision.id
        project.updated_at = utcnow()
        payload.setdefault("run_id", str(run.id))
        payload.setdefault("revision_id", str(revision.id))
        payload.setdefault("revision_number", revision.revision_number)
        payload.setdefault("preview_manifest", revision.preview_manifest or {"pages": []})
        event.payload = dict(payload)
        await db.flush()
        fallback_text = str(
            payload.get("message") or payload.get("summary") or "PPT 已生成完成"
        )
        await _persist_terminal_assistant(
            db,
            run=run,
            project=project,
            fallback_text=fallback_text,
            fallback_tool_calls=payload.get("tool_calls"),
        )
    elif event_type == "error":
        message = str(payload.get("message") or payload.get("reason") or "PPT Agent 执行失败")
        run.status = PresentationRunStatus.FAILED
        run.error_message = message
        run.completed_at = utcnow()
        revision.status = PresentationRevisionStatus.FAILED
        revision.error_message = message
        event.payload = dict(payload)
        await db.flush()
        await _persist_terminal_assistant(
            db,
            run=run,
            project=project,
            fallback_text=f"任务未完成：{message}",
            response_status=MessageResponseStatus.STOPPED,
        )
    elif event_type == "cancelled":
        run.status = PresentationRunStatus.CANCELLED
        run.completed_at = utcnow()
        revision.status = PresentationRevisionStatus.FAILED
        revision.error_message = "已取消"
        event.payload = dict(payload)
        await db.flush()
        await _persist_terminal_assistant(
            db,
            run=run,
            project=project,
            fallback_text="任务已停止。",
            response_status=MessageResponseStatus.STOPPED,
        )
    if commit:
        await db.commit()
        await db.refresh(event)
    return event


async def build_run_message_trace(
    db: AsyncSession,
    run_id: UUID,
    fallback_text: str,
) -> tuple[str, dict[str, Any], list[dict[str, Any]]]:
    """Rebuild the persisted assistant timeline from resumable run events."""

    events = list(
        (
            await db.scalars(
                select(TeacherPresentationEvent)
                .where(TeacherPresentationEvent.run_id == run_id)
                .order_by(TeacherPresentationEvent.sequence)
            )
        ).all()
    )
    run = await db.get(TeacherPresentationRun, run_id)
    segments: list[dict[str, Any]] = []
    thinking_parts: list[str] = []
    thinking_windows: dict[int, dict[str, datetime | None]] = {}
    final_tools: dict[str, dict[str, Any]] = {}

    for event in events:
        payload = event.payload or {}
        if event.event_type == "thinking_delta":
            content = str(payload.get("content") or payload.get("delta") or "")
            if content:
                thinking_parts.append(content)
                iteration = int(payload.get("iteration") or 0)
                window = thinking_windows.setdefault(
                    iteration,
                    {"start": event.created_at, "last": event.created_at, "end": None},
                )
                window["last"] = event.created_at
            continue

        if event.event_type == "text_delta":
            content = str(payload.get("content") or payload.get("delta") or "")
            if not content:
                continue
            iteration = int(payload.get("iteration") or 0)
            if iteration in thinking_windows and thinking_windows[iteration]["end"] is None:
                thinking_windows[iteration]["end"] = event.created_at
            if segments and segments[-1].get("type") == "text":
                segments[-1]["content"] += content
            else:
                segments.append({"type": "text", "content": content})
            continue

        if event.event_type != "tool_call":
            continue
        call_id = str(payload.get("id") or "")
        name = str(payload.get("name") or payload.get("tool") or "")
        if not call_id:
            continue
        iteration = int(payload.get("iteration") or 0)
        if iteration in thinking_windows and thinking_windows[iteration]["end"] is None:
            thinking_windows[iteration]["end"] = event.created_at
        tool = final_tools.setdefault(
            call_id,
            {"id": call_id, "name": name, "tool": name, "status": "running"},
        )
        tool.update(
            {
                key: payload[key]
                for key in ("name", "tool", "status", "arguments", "result", "error")
                if key in payload
            }
        )
        segment = next(
            (
                item
                for item in reversed(segments)
                if item.get("type") == "tool" and item.get("id") == call_id
            ),
            None,
        )
        if segment is None:
            segment = {"type": "tool", **tool}
            segments.append(segment)
        else:
            segment.update(tool)

    if run and run.status in TERMINAL_RUN_STATUSES:
        terminal_error = run.error_message or (
            "任务已取消" if run.status == PresentationRunStatus.CANCELLED else "任务中断"
        )
        for tool in final_tools.values():
            if tool.get("status") == "running":
                tool.update({"status": "error", "error": terminal_error})
        for segment in segments:
            if segment.get("type") == "tool" and segment.get("status") == "running":
                segment.update({"status": "error", "error": terminal_error})

    text_segments = [str(item.get("content") or "") for item in segments if item.get("type") == "text"]
    assistant_text = "\n\n".join(item for item in text_segments if item).strip() or fallback_text
    thinking_content = "".join(thinking_parts)
    thinking_duration = sum(
        max(
            (
                (window["end"] or window["last"] or window["start"])
                - window["start"]
            ).total_seconds(),
            0.0,
        )
        for window in thinking_windows.values()
        if window["start"] is not None
    )
    llm_context = {
        "run_id": str(run_id),
        "run_status": run.status.value if run else None,
        "stream_sequence": events[-1].sequence if events else 0,
        "segments": segments,
        "presentation_segments": segments,
        "thinking_content": thinking_content,
        "thinking_duration": round(thinking_duration, 3),
    }
    return assistant_text, llm_context, list(final_tools.values())


async def _materialize_ready_payload(
    db: AsyncSession,
    project: TeacherPresentationProject,
    revision: TeacherPresentationRevision,
    payload: dict[str, Any],
) -> None:
    output_dir = private_root() / str(project.id) / "revisions" / str(revision.id)
    output_dir.mkdir(parents=True, exist_ok=True)
    encoded = payload.get("pptx_base64")
    supplied_path = payload.get("pptx_path")
    if encoded:
        pptx_path = output_dir / "presentation.pptx"
        try:
            pptx_path.write_bytes(base64.b64decode(encoded, validate=True))
        except Exception as exc:
            raise HTTPException(status_code=422, detail="无效的 PPTX base64") from exc
    elif supplied_path:
        pptx_path = resolve_private_path(str(supplied_path))
    else:
        raise HTTPException(status_code=422, detail="presentation_ready 缺少 PPTX 产物")

    previews: list[dict[str, Any]] = []
    for index, item in enumerate(payload.get("previews") or [], start=1):
        if not isinstance(item, dict) or not item.get("image_base64"):
            continue
        page = int(item.get("page", index))
        preview_path = output_dir / f"slide-{page}.png"
        try:
            preview_path.write_bytes(base64.b64decode(item["image_base64"], validate=True))
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"第 {page} 页预览无效") from exc
        preview_asset = TeacherPresentationAsset(
            project_id=project.id,
            revision_id=revision.id,
            kind=PresentationAssetKind.PREVIEW,
            filename=preview_path.name,
            private_path=str(preview_path),
            mime_type="image/png",
            file_size=preview_path.stat().st_size,
            asset_metadata={"page": page},
        )
        db.add(preview_asset)
        await db.flush()
        previews.append({"page": page, "asset_id": str(preview_asset.id)})

    revision.status = PresentationRevisionStatus.COMPLETED
    revision.summary = str(payload.get("summary") or "") or None
    revision.manifest = payload.get("manifest") or {}
    revision.preview_manifest = {"pages": previews}
    revision.pptx_path = str(pptx_path)
    revision.completed_at = utcnow()
    db.add(
        TeacherPresentationAsset(
            project_id=project.id,
            revision_id=revision.id,
            kind=PresentationAssetKind.PPTX,
            filename=f"{project.title}.pptx",
            private_path=str(pptx_path),
            mime_type=PPTX_MIME,
            file_size=pptx_path.stat().st_size,
        )
    )


async def list_revisions(
    db: AsyncSession, project_id: UUID
) -> list[TeacherPresentationRevision]:
    return list(
        (
            await db.scalars(
                select(TeacherPresentationRevision)
                .where(
                    TeacherPresentationRevision.project_id == project_id,
                    TeacherPresentationRevision.status
                    == PresentationRevisionStatus.COMPLETED,
                )
                .order_by(TeacherPresentationRevision.revision_number.desc())
            )
        ).all()
    )


async def get_revision(
    db: AsyncSession, project_id: UUID, revision_id: UUID, *, completed: bool = False
) -> TeacherPresentationRevision:
    revision = await db.scalar(
        select(TeacherPresentationRevision).where(
            TeacherPresentationRevision.id == revision_id,
            TeacherPresentationRevision.project_id == project_id,
        )
    )
    if revision is None or (completed and revision.status != PresentationRevisionStatus.COMPLETED):
        raise HTTPException(status_code=404, detail="PPT 版本不存在或尚未完成")
    return revision


async def restore_revision(
    db: AsyncSession, project: TeacherPresentationProject, revision_id: UUID
) -> TeacherPresentationRevision:
    revision = await get_revision(db, project.id, revision_id, completed=True)
    project.current_revision_id = revision.id
    project.updated_at = utcnow()
    await db.commit()
    return revision


async def cancel_run(
    db: AsyncSession,
    *,
    project: TeacherPresentationProject,
    run_id: UUID,
    manager: SandboxManagerClient | None = None,
) -> TeacherPresentationRun:
    run = await db.scalar(
        select(TeacherPresentationRun).where(
            TeacherPresentationRun.id == run_id,
            TeacherPresentationRun.project_id == project.id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="run 不存在")
    if run.status in TERMINAL_RUN_STATUSES:
        return run
    if run.manager_run_id:
        await (manager or SandboxManagerClient()).cancel_run(run.manager_run_id)
    await append_event(
        db,
        run=run,
        project=project,
        sequence=None,
        event_type="cancelled",
        payload={"message": "教师已取消任务"},
    )
    return run


async def resume_run(
    db: AsyncSession,
    *,
    project: TeacherPresentationProject,
    run_id: UUID,
    gateway_url: str,
    manager: SandboxManagerClient | None = None,
) -> TeacherPresentationRun:
    run = await db.scalar(
        select(TeacherPresentationRun).where(
            TeacherPresentationRun.id == run_id,
            TeacherPresentationRun.project_id == project.id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="run 不存在")
    revision = await db.get(TeacherPresentationRevision, run.revision_id)
    resumable_conversation = (
        run.status == PresentationRunStatus.COMPLETED
        and revision.status != PresentationRevisionStatus.COMPLETED
        and not revision.pptx_path
    )
    if run.status not in {
        PresentationRunStatus.FAILED,
        PresentationRunStatus.CANCELLED,
        PresentationRunStatus.RECOVERING,
    } and not resumable_conversation:
        raise HTTPException(status_code=409, detail="当前 run 不需要恢复")
    token = secrets.token_urlsafe(48)
    run.capability_token_hash = _token_hash(token)
    run.capability_expires_at = utcnow() + timedelta(hours=6)
    run.status = PresentationRunStatus.RECOVERING
    run.attempt_count = 1
    run.retry_deadline_at = utcnow() + timedelta(minutes=30)
    run.completed_at = None
    run.error_message = None
    revision.status = PresentationRevisionStatus.DRAFT
    revision.error_message = None
    await append_event(
        db,
        run=run,
        project=project,
        sequence=None,
        event_type="recovery_started",
        payload={"stage": "recovery_queued", "attempt": 1, "run_id": str(run.id)},
    )
    payload = {
        "run_id": str(run.id),
        "project_id": str(project.id),
        "revision_id": str(revision.id),
        "space_id": str(project.space_id),
        "user_id": str(project.teacher_user_id),
        "instruction": run.prompt,
        "gateway_url": f"{gateway_url.rstrip('/')}/{run.id}",
        "capability_token": token,
        "max_iterations": 60,
        "max_seconds": 1800,
        "max_attempts": 5,
        "reset_iterations": True,
        "retry_backoff_seconds": [2, 5, 10, 20, 30],
        "metadata": {
            "revision_id": str(revision.id),
            "parent_revision_id": (
                str(revision.parent_revision_id) if revision.parent_revision_id else None
            ),
            "source_ids": list((revision.manifest or {}).get("source_ids", [])),
        },
    }
    try:
        data = await (manager or SandboxManagerClient()).resume_run(
            run.manager_run_id or str(run.id), payload
        )
    except Exception as exc:
        await append_event(
            db,
            run=run,
            project=project,
            sequence=None,
            event_type="error",
            payload={
                "message": "PPT Agent 恢复失败",
                "detail": str(exc).strip() or exc.__class__.__name__,
                "error_type": exc.__class__.__name__,
                "stage": "manager_resume",
            },
        )
        raise HTTPException(status_code=502, detail="PPT Agent 恢复失败") from exc
    run.manager_run_id = str(data.get("run_id") or data.get("id") or run.id)
    await db.commit()
    await db.refresh(run)
    return run


async def refresh_run_status(
    db: AsyncSession,
    run: TeacherPresentationRun,
    manager: SandboxManagerClient | None = None,
) -> TeacherPresentationRun:
    if not run.manager_run_id or run.status in TERMINAL_RUN_STATUSES:
        return run
    try:
        remote = await (manager or SandboxManagerClient()).get_run(run.manager_run_id)
    except SandboxManagerError:
        return run
    remote_status = str(remote.get("status", "unknown"))
    run.attempt_count = max(run.attempt_count, int(remote.get("attempt") or 1))
    if remote_status in {"starting", "running"}:
        run.status = PresentationRunStatus.RUNNING
        run.started_at = run.started_at or utcnow()
    elif remote_status == "recovering":
        run.status = PresentationRunStatus.RECOVERING
        run.completed_at = None
        revision = await db.get(TeacherPresentationRevision, run.revision_id)
        if revision.status != PresentationRevisionStatus.COMPLETED:
            revision.status = PresentationRevisionStatus.DRAFT
            revision.error_message = None
    elif remote_status in {"failed", "cancelled"}:
        terminal_type = "cancelled" if remote_status == "cancelled" else "error"
        terminal_exists = await db.scalar(
            select(TeacherPresentationEvent.id).where(
                TeacherPresentationEvent.run_id == run.id,
                TeacherPresentationEvent.event_type == terminal_type,
            )
        )
        if terminal_exists is None:
            message = str(remote.get("error") or remote_status)
            await append_event(
                db,
                run=run,
                project=await db.get(TeacherPresentationProject, run.project_id),
                sequence=None,
                event_type=terminal_type,
                payload={"message": message},
                commit=False,
            )
    elif remote_status == "succeeded":
        revision = await db.get(TeacherPresentationRevision, run.revision_id)
        if revision.status == PresentationRevisionStatus.COMPLETED:
            run.status = PresentationRunStatus.COMPLETED
            run.completed_at = run.completed_at or utcnow()
        else:
            message = "PPT Agent 已退出，但没有提交可用的 PPTX 产物"
            await append_event(
                db,
                run=run,
                project=await db.get(TeacherPresentationProject, run.project_id),
                sequence=None,
                event_type="error",
                payload={"message": message},
                commit=False,
            )
    await db.commit()
    return run


async def get_course_graph_overview(db: AsyncSession, space_id: UUID) -> dict[str, Any]:
    nodes = list(
        (
            await db.execute(
                select(Node.id, Node.label).where(Node.space_id == space_id).order_by(Node.label, Node.id)
            )
        ).all()
    )
    edges = list(
        (
            await db.execute(
                select(Edge.from_node_id, Edge.to_node_id, Edge.type)
                .where(
                    Edge.space_id == space_id,
                    Edge.type.in_([EdgeType.KNOWLEDGE_TREE, EdgeType.ADVANCED]),
                    Edge.user_id.is_(None),
                )
                .order_by(Edge.type, Edge.from_node_id, Edge.to_node_id)
            )
        ).all()
    )
    # Deliberately return no mastery property and no learning_path edges.
    return {
        "nodes": [{"id": str(row.id), "label": row.label} for row in nodes],
        "edges": [
            {
                "from_node_id": str(row.from_node_id),
                "to_node_id": str(row.to_node_id),
                "type": row.type.value,
            }
            for row in edges
        ],
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


async def execute_capability_tool(
    db: AsyncSession,
    *,
    run: TeacherPresentationRun,
    project: TeacherPresentationProject,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if tool_name == "get_course_graph_overview":
        return {"success": True, "data": await get_course_graph_overview(db, run.space_id)}

    if tool_name in {"list_documents", "search_keywords", "read_document", "view_document_page"}:
        result = await RAGToolExecutor(run.space_id).execute(tool_name, arguments)
        payload = result.to_dict()
        if result.image_base64:
            image_dir = private_root() / str(project.id) / "document-pages"
            image_dir.mkdir(parents=True, exist_ok=True)
            image_path = image_dir / f"{uuid4().hex}.png"
            image_path.write_bytes(base64.b64decode(result.image_base64))
            asset = TeacherPresentationAsset(
                project_id=project.id,
                revision_id=run.revision_id,
                kind=PresentationAssetKind.GENERATED_IMAGE,
                filename=image_path.name,
                private_path=str(image_path),
                mime_type="image/png",
                file_size=image_path.stat().st_size,
                asset_metadata={
                    "source": "course_document_page",
                    "document_id": arguments.get("document_id"),
                    "page_number": arguments.get("page_number"),
                },
            )
            db.add(asset)
            await db.commit()
            data = dict(payload.get("data") or {})
            data.update(
                {
                    "asset_id": str(asset.id),
                    "filename": asset.filename,
                    "download_url": f"assets/{asset.id}",
                }
            )
            payload["data"] = data
        return payload

    if tool_name == "get_class_knowledge_summary":
        days = int(arguments.get("days", 30))
        if days not in {7, 30, 90}:
            return {"success": False, "message": "days 仅支持 7、30、90"}
        data = await TeacherAnalyticsService(db, run.space_id, days).get_knowledge()
        return {"success": True, "data": data.model_dump(mode="json")}

    if tool_name == "generate_image":
        result = await ImageToolExecutor().execute("generate_image", arguments)
        payload = result.to_dict()
        if result.success and result.image_base64:
            image_dir = private_root() / str(project.id) / "generated"
            image_dir.mkdir(parents=True, exist_ok=True)
            image_path = image_dir / f"{uuid4().hex}.png"
            image_path.write_bytes(base64.b64decode(result.image_base64))
            asset = TeacherPresentationAsset(
                project_id=project.id,
                revision_id=run.revision_id,
                kind=PresentationAssetKind.GENERATED_IMAGE,
                filename=image_path.name,
                private_path=str(image_path),
                mime_type="image/png",
                file_size=image_path.stat().st_size,
                asset_metadata={"description": arguments.get("description")},
            )
            db.add(asset)
            await db.commit()
            public_url = str((result.data or {}).get("image_url") or "")
            if public_url:
                upload_root = Path(get_settings().upload_dir).resolve()
                prefix = f"/{upload_root.name}/"
                if public_url.startswith(prefix):
                    public_path = (upload_root / public_url[len(prefix):]).resolve()
                    if upload_root in public_path.parents:
                        with suppress(OSError):
                            public_path.unlink(missing_ok=True)
            payload["data"] = {
                "asset_id": str(asset.id),
                "filename": asset.filename,
                "download_url": f"assets/{asset.id}",
                "description": (result.data or {}).get("description", ""),
            }
        return payload

    if tool_name == "publish_presentation_to_space":
        # The sandbox may request confirmation for an existing completed
        # revision, but can never self-confirm publishing.
        requested_revision_id = arguments.get("revision_id") or project.current_revision_id
        try:
            target_revision_id = UUID(str(requested_revision_id))
        except (TypeError, ValueError):
            return {
                "success": False,
                "message": "没有可发布的已完成 PPT 版本",
            }
        revision = await db.scalar(
            select(TeacherPresentationRevision).where(
                TeacherPresentationRevision.id == target_revision_id,
                TeacherPresentationRevision.project_id == project.id,
                TeacherPresentationRevision.status == PresentationRevisionStatus.COMPLETED,
            )
        )
        if revision is None:
            return {"success": False, "message": "仅已完成且属于当前项目的版本可以请求发布"}
        await append_event(
            db,
            run=run,
            project=project,
            sequence=None,
            event_type="publish_confirmation_required",
            payload={
                "revision_id": str(revision.id),
                "revision_number": revision.revision_number,
                "message": "PPT 已准备好，是否发布到学习空间资料库？",
            },
        )
        return {
            "success": False,
            "requires_confirmation": True,
            "message": "发布属于教师显式操作，请在教师端确认后调用 publish API",
            "revision_id": str(revision.id),
        }

    raise HTTPException(status_code=404, detail=f"未授权的 capability: {tool_name}")


async def publish_revision(
    db: AsyncSession,
    *,
    project: TeacherPresentationProject,
    revision: TeacherPresentationRevision,
    publisher_user_id: UUID,
    title: str | None,
) -> TeacherPresentationPublication:
    source = resolve_private_path(revision.pptx_path or "")
    settings = get_settings()
    documents_dir = Path(settings.upload_dir) / "documents"
    documents_dir.mkdir(parents=True, exist_ok=True)
    destination = documents_dir / f"presentation-{project.id}-{uuid4().hex}.pptx"
    await _copy_file(source, destination)
    file_url = f"/uploads/documents/{destination.name}"
    document: SpaceDocument | None = None
    old_published_path: Path | None = None
    try:
        if project.published_document_id:
            document = await db.scalar(
                select(SpaceDocument).where(
                    SpaceDocument.id == project.published_document_id,
                    SpaceDocument.space_id == project.space_id,
                )
            )
        if document is None:
            document = SpaceDocument(
                space_id=project.space_id,
                doc_type=DocumentType.DOCUMENT,
                title=(title or project.title).strip(),
                url=file_url,
                original_filename=f"{(title or project.title).strip()}.pptx",
                file_size=destination.stat().st_size,
                mime_type=PPTX_MIME,
                creator_user_id=publisher_user_id,
            )
            db.add(document)
            await db.flush()
            project.published_document_id = document.id
        else:
            old_url = str(document.url or "")
            public_prefix = f"/{Path(settings.upload_dir).resolve().name}/documents/"
            if old_url.startswith(public_prefix):
                candidate = (documents_dir / old_url[len(public_prefix):]).resolve()
                if documents_dir.resolve() in candidate.parents:
                    old_published_path = candidate
            document.title = (title or document.title or project.title).strip()
            document.url = file_url
            document.original_filename = f"{document.title}.pptx"
            document.file_size = destination.stat().st_size
            document.mime_type = PPTX_MIME
            document.creator_user_id = publisher_user_id
        publication = TeacherPresentationPublication(
            project_id=project.id,
            revision_id=revision.id,
            document_id=document.id,
            publisher_user_id=publisher_user_id,
        )
        db.add(publication)
        await db.commit()
        await db.refresh(publication)
    except Exception:
        await db.rollback()
        destination.unlink(missing_ok=True)
        raise
    if old_published_path and old_published_path != destination.resolve():
        with suppress(OSError):
            old_published_path.unlink(missing_ok=True)
    schedule_document_processing(document.id)
    return publication


async def _copy_file(source: Path, destination: Path) -> None:
    import asyncio

    await asyncio.to_thread(shutil.copyfile, source, destination)


def sse_event(event_type: str, payload: dict[str, Any], event_id: int | None = None) -> str:
    fields = []
    if event_id is not None:
        fields.append(f"id: {event_id}")
    fields.append(f"event: {event_type}")
    fields.append(f"data: {json.dumps(payload, ensure_ascii=False, default=str)}")
    return "\n".join(fields) + "\n\n"


async def save_gateway_artifact(
    db: AsyncSession,
    *,
    run: TeacherPresentationRun,
    project: TeacherPresentationProject,
    upload: UploadFile,
    kind: PresentationAssetKind,
    metadata: dict[str, Any] | None = None,
) -> TeacherPresentationAsset:
    """Accept a sandbox output without trusting container-local paths."""
    filename = Path(upload.filename or f"artifact-{uuid4().hex}").name
    output_dir = private_root() / str(project.id) / "revisions" / str(run.revision_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".pptx" if kind == PresentationAssetKind.PPTX else (Path(filename).suffix or ".png")
    destination = output_dir / f"{kind.value}-{uuid4().hex}{suffix}"
    size = 0
    try:
        async with aiofiles.open(destination, "wb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_SOURCE_BYTES:
                    raise HTTPException(status_code=413, detail="artifact 最大 50 MB")
                await output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()

    asset = TeacherPresentationAsset(
        project_id=project.id,
        revision_id=run.revision_id,
        kind=kind,
        filename=filename,
        private_path=str(destination),
        mime_type=upload.content_type or mimetypes.guess_type(filename)[0],
        file_size=size,
        asset_metadata=metadata,
    )
    db.add(asset)
    revision = await db.get(TeacherPresentationRevision, run.revision_id)
    if kind == PresentationAssetKind.PPTX:
        revision.pptx_path = str(destination)
    elif kind == PresentationAssetKind.PREVIEW:
        manifest = dict(revision.preview_manifest or {})
        pages = list(manifest.get("pages") or [])
        await db.flush()
        page_number = (metadata or {}).get("page", (metadata or {}).get("slide_number", len(pages) + 1))
        pages.append({"page": int(page_number), "asset_id": str(asset.id)})
        manifest["pages"] = sorted(pages, key=lambda item: item["page"])
        revision.preview_manifest = manifest
    await db.commit()
    await db.refresh(asset)
    return asset
