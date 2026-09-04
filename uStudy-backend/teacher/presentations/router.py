"""Teacher-only public API for Presentation Agent projects."""

from __future__ import annotations

import asyncio
import os
from datetime import timedelta
from typing import Annotated, AsyncGenerator
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db, get_scoped_session
from db.models import (
    Message,
    PresentationAssetKind,
    PresentationRunStatus,
    TeacherPresentationAsset,
    TeacherPresentationEvent,
    TeacherPresentationProject,
    TeacherPresentationRevision,
    TeacherPresentationRun,
    User,
)
from teacher.dependencies import require_course_teacher
from teacher.presentations.schemas import (
    AssetResponse,
    ConversationMessageResponse,
    MessageCreate,
    ProjectCreate,
    ProjectResponse,
    PublicationResponse,
    PublishRequest,
    RevisionResponse,
    RunResponse,
)
from teacher.presentations.service import (
    ACTIVE_RUN_STATUSES,
    TERMINAL_RUN_STATUSES,
    build_run_message_trace,
    cancel_run,
    create_project,
    create_run,
    delete_source,
    get_owned_project,
    get_revision,
    list_projects,
    list_revisions,
    publish_revision,
    refresh_run_status,
    resolve_private_path,
    restore_revision,
    save_source,
    sse_event,
)
from teacher.presentations.service import (
    resume_run as resume_failed_run,
)

router = APIRouter(prefix="/spaces/{space_id}/presentations", tags=["teacher-presentations"])


async def _project_response(
    db: AsyncSession, project: TeacherPresentationProject
) -> ProjectResponse:
    latest = await db.scalar(
        select(TeacherPresentationRun)
        .where(
            TeacherPresentationRun.project_id == project.id,
        )
        .order_by(TeacherPresentationRun.created_at.desc())
        .limit(1)
    )
    return ProjectResponse.model_validate(project).model_copy(
        update={
            "active_run_id": latest.id if latest and latest.status in ACTIVE_RUN_STATUSES else None,
            "status": latest.status.value if latest else "idle",
        }
    )


async def _run_response(db: AsyncSession, run: TeacherPresentationRun) -> RunResponse:
    maximum = await db.scalar(
        select(func.max(TeacherPresentationEvent.sequence)).where(
            TeacherPresentationEvent.run_id == run.id
        )
    )
    return RunResponse.model_validate(run).model_copy(
        update={"last_sequence": int(maximum or 0)}
    )


async def _stream_run_events(run_id: UUID, cursor: int = 0) -> AsyncGenerator[str, None]:
    """Replay persisted events and continue tailing one existing sandbox run."""

    heartbeat_ticks = 0
    while True:
        async with get_scoped_session() as session:
            if heartbeat_ticks and heartbeat_ticks % 20 == 0:
                run_record = await session.get(TeacherPresentationRun, run_id)
                if run_record is not None:
                    await refresh_run_status(session, run_record)
            events = list(
                (
                    await session.scalars(
                        select(TeacherPresentationEvent)
                        .where(
                            TeacherPresentationEvent.run_id == run_id,
                            TeacherPresentationEvent.sequence > cursor,
                        )
                        .order_by(TeacherPresentationEvent.sequence)
                    )
                ).all()
            )
            current_status = await session.scalar(
                select(TeacherPresentationRun.status).where(
                    TeacherPresentationRun.id == run_id
                )
            )
            artifact_ready = bool(
                await session.scalar(
                    select(TeacherPresentationRevision.pptx_path)
                    .join(
                        TeacherPresentationRun,
                        TeacherPresentationRun.revision_id
                        == TeacherPresentationRevision.id,
                    )
                    .where(TeacherPresentationRun.id == run_id)
                )
            )
        for event in events:
            cursor = event.sequence
            # Keep the cursor in both the SSE ``id`` field and JSON payload.  The
            # shared uni-app SSE client exposes event data but not the raw id.
            yield sse_event(
                event.event_type,
                {**(event.payload or {}), "sequence": event.sequence},
                event.sequence,
            )
        if current_status in TERMINAL_RUN_STATUSES and not events:
            yield sse_event(
                "done",
                {
                    "run_id": str(run_id),
                    "status": current_status.value,
                    "artifact_ready": artifact_ready,
                },
            )
            return
        heartbeat_ticks += 1
        if heartbeat_ticks % 30 == 0:
            yield ": heartbeat\n\n"
        await asyncio.sleep(0.5)


def _event_stream_response(run_id: UUID, cursor: int = 0) -> StreamingResponse:
    return StreamingResponse(
        _stream_run_events(run_id, max(cursor, 0)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_presentation_project(
    space_id: UUID,
    request: ProjectCreate,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project = await create_project(
        db, space_id=space_id, user_id=user.id, title=request.title
    )
    return await _project_response(db, project)


@router.get("", response_model=list[ProjectResponse])
async def get_presentation_projects(
    space_id: UUID,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    projects = await list_projects(db, space_id=space_id, user_id=user.id)
    return [await _project_response(db, project) for project in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_presentation_project(
    space_id: UUID,
    project_id: UUID,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project = await get_owned_project(db, project_id, user.id, space_id)
    return await _project_response(db, project)


@router.get("/{project_id}/messages", response_model=list[ConversationMessageResponse])
async def get_presentation_messages(
    space_id: UUID,
    project_id: UUID,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationMessageResponse]:
    project = await get_owned_project(db, project_id, user.id, space_id)
    stored_messages = list(
        (
            await db.scalars(
                select(Message)
                .where(Message.conversation_id == project.conversation_id)
                .order_by(Message.created_at, Message.id)
            )
        ).all()
    )
    runs = list(
        (
            await db.scalars(
                select(TeacherPresentationRun)
                .where(TeacherPresentationRun.project_id == project.id)
                .order_by(TeacherPresentationRun.created_at, TeacherPresentationRun.id)
            )
        ).all()
    )
    run_map = {str(run.id): run for run in runs}
    maxima = dict(
        (
            await db.execute(
                select(
                    TeacherPresentationEvent.run_id,
                    func.max(TeacherPresentationEvent.sequence),
                )
                .join(
                    TeacherPresentationRun,
                    TeacherPresentationRun.id == TeacherPresentationEvent.run_id,
                )
                .where(TeacherPresentationRun.project_id == project.id)
                .group_by(TeacherPresentationEvent.run_id)
            )
        ).all()
    )
    last_errors: dict[UUID, dict] = {}
    error_events = list(
        (
            await db.scalars(
                select(TeacherPresentationEvent)
                .join(
                    TeacherPresentationRun,
                    TeacherPresentationRun.id == TeacherPresentationEvent.run_id,
                )
                .where(
                    TeacherPresentationRun.project_id == project.id,
                    TeacherPresentationEvent.event_type == "error",
                )
                .order_by(TeacherPresentationEvent.sequence)
            )
        ).all()
    )
    for error_event in error_events:
        last_errors[error_event.run_id] = error_event.payload or {}

    def run_recoverable(run: TeacherPresentationRun | None) -> bool:
        if run is None:
            return False
        if run.status == PresentationRunStatus.CANCELLED:
            return True
        if run.status != PresentationRunStatus.FAILED:
            return False
        return last_errors.get(run.id, {}).get("retryable") is not False
    responses: list[ConversationMessageResponse] = []
    represented_runs: set[str] = set()
    for message in stored_messages:
        context = message.llm_context or {}
        raw_run_id = str(context.get("run_id") or "")
        run = run_map.get(raw_run_id)
        if raw_run_id:
            represented_runs.add(raw_run_id)
        responses.append(
            ConversationMessageResponse.model_validate(message).model_copy(
                update={
                    "run_id": run.id if run else None,
                    "run_status": run.status.value if run else context.get("run_status"),
                    "stream_sequence": int(
                        maxima.get(run.id, context.get("stream_sequence", 0)) if run else context.get("stream_sequence", 0)
                    ),
                    "streaming": bool(run and run.status in ACTIVE_RUN_STATUSES),
                    "recoverable": run_recoverable(run),
                    "run_error": (
                        str(last_errors.get(run.id, {}).get("message") or run.error_message or "")
                        if run
                        else None
                    )
                    or None,
                }
            )
        )

    # Runs created before terminal assistant persistence are reconstructed from
    # their durable events. Completed legacy runs already have a normal assistant
    # message without run_id, so only synthesize non-completed runs here.
    for run in runs:
        if str(run.id) in represented_runs or run.status == PresentationRunStatus.COMPLETED:
            continue
        fallback = (
            "任务已停止。"
            if run.status == PresentationRunStatus.CANCELLED
            else f"任务未完成：{run.error_message or 'PPT Agent 执行失败'}"
            if run.status == PresentationRunStatus.FAILED
            else "正在恢复课件任务。"
        )
        content, context, tool_calls = await build_run_message_trace(db, run.id, fallback)
        responses.append(
            ConversationMessageResponse(
                id=run.id,
                role="assistant",
                content=content,
                llm_context=context,
                tool_calls=tool_calls or None,
                created_at=run.created_at + timedelta(microseconds=1),
                run_id=run.id,
                run_status=run.status.value,
                stream_sequence=int(maxima.get(run.id, 0)),
                streaming=run.status in ACTIVE_RUN_STATUSES,
                recoverable=run_recoverable(run),
                run_error=str(
                    last_errors.get(run.id, {}).get("message") or run.error_message or ""
                )
                or None,
            )
        )
    responses.sort(key=lambda item: (item.created_at, item.role == "assistant", str(item.id)))
    return responses


@router.post("/{project_id}/sources", response_model=AssetResponse, status_code=201)
async def upload_source(
    space_id: UUID,
    project_id: UUID,
    kind: Annotated[str, Form()] = "source",
    file: Annotated[UploadFile, File()] = None,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssetResponse:
    if file is None:
        raise HTTPException(status_code=422, detail="file 必填")
    try:
        asset_kind = PresentationAssetKind(kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="kind 仅支持 source 或 template") from exc
    if asset_kind not in {PresentationAssetKind.SOURCE, PresentationAssetKind.TEMPLATE}:
        raise HTTPException(status_code=422, detail="kind 仅支持 source 或 template")
    project = await get_owned_project(db, project_id, user.id, space_id)
    return await save_source(db, project=project, upload=file, kind=asset_kind)


@router.get("/{project_id}/sources", response_model=list[AssetResponse])
async def get_sources(
    space_id: UUID,
    project_id: UUID,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[AssetResponse]:
    project = await get_owned_project(db, project_id, user.id, space_id)
    return list(
        (
            await db.scalars(
                select(TeacherPresentationAsset)
                .where(
                    TeacherPresentationAsset.project_id == project.id,
                    TeacherPresentationAsset.kind.in_(
                        [PresentationAssetKind.SOURCE, PresentationAssetKind.TEMPLATE]
                    ),
                )
                .order_by(TeacherPresentationAsset.created_at)
            )
        ).all()
    )


@router.delete("/{project_id}/sources/{asset_id}")
async def remove_source(
    space_id: UUID,
    project_id: UUID,
    asset_id: UUID,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    project = await get_owned_project(db, project_id, user.id, space_id)
    await delete_source(db, project=project, asset_id=asset_id)
    return {"deleted": True}


@router.post("/{project_id}/messages")
async def send_presentation_message(
    space_id: UUID,
    project_id: UUID,
    payload: MessageCreate,
    last_event_id: int = Header(0, alias="Last-Event-ID"),
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    project = await get_owned_project(db, project_id, user.id, space_id)
    from config import get_settings

    settings = get_settings()
    internal_base = (
        getattr(settings, "presentation_agent_gateway_base_url", None)
        or os.getenv(
            "PRESENTATION_AGENT_GATEWAY_BASE_URL",
            "http://backend:8000/api/internal/presentation-agent/runs",
        )
    ).rstrip("/")
    run, _ = await create_run(
        db,
        project=project,
        content=payload.content,
        gateway_url=internal_base,
        source_ids=payload.source_ids,
        expected_revision_id=payload.expected_revision_id,
    )

    return _event_stream_response(run.id, last_event_id)


@router.get("/{project_id}/runs/{run_id}/events")
async def resume_presentation_run_events(
    space_id: UUID,
    project_id: UUID,
    run_id: UUID,
    after: int = Query(0, ge=0),
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    project = await get_owned_project(db, project_id, user.id, space_id)
    run = await db.scalar(
        select(TeacherPresentationRun).where(
            TeacherPresentationRun.id == run_id,
            TeacherPresentationRun.project_id == project.id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="run 不存在")
    return _event_stream_response(run.id, after)


@router.get("/{project_id}/runs/{run_id}", response_model=RunResponse)
async def get_presentation_run(
    space_id: UUID,
    project_id: UUID,
    run_id: UUID,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    project = await get_owned_project(db, project_id, user.id, space_id)
    run = await db.scalar(
        select(TeacherPresentationRun).where(
            TeacherPresentationRun.id == run_id,
            TeacherPresentationRun.project_id == project.id,
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="run 不存在")
    return await _run_response(db, await refresh_run_status(db, run))


@router.post("/{project_id}/runs/{run_id}/cancel", response_model=RunResponse)
async def cancel_presentation_run(
    space_id: UUID,
    project_id: UUID,
    run_id: UUID,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    project = await get_owned_project(db, project_id, user.id, space_id)
    return await _run_response(db, await cancel_run(db, project=project, run_id=run_id))


@router.post("/{project_id}/runs/{run_id}/resume", response_model=RunResponse)
async def resume_presentation_run(
    space_id: UUID,
    project_id: UUID,
    run_id: UUID,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> RunResponse:
    project = await get_owned_project(db, project_id, user.id, space_id)
    from config import get_settings

    settings = get_settings()
    internal_base = (
        getattr(settings, "presentation_agent_gateway_base_url", None)
        or os.getenv(
            "PRESENTATION_AGENT_GATEWAY_BASE_URL",
            "http://backend:8000/api/internal/presentation-agent/runs",
        )
    ).rstrip("/")
    run = await resume_failed_run(
        db,
        project=project,
        run_id=run_id,
        gateway_url=internal_base,
    )
    return await _run_response(db, run)


@router.get("/{project_id}/revisions", response_model=list[RevisionResponse])
async def get_presentation_revisions(
    space_id: UUID,
    project_id: UUID,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[RevisionResponse]:
    project = await get_owned_project(db, project_id, user.id, space_id)
    return await list_revisions(db, project.id)


@router.post("/{project_id}/revisions/{revision_id}/restore", response_model=RevisionResponse)
async def restore_presentation_revision(
    space_id: UUID,
    project_id: UUID,
    revision_id: UUID,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> RevisionResponse:
    project = await get_owned_project(db, project_id, user.id, space_id)
    return await restore_revision(db, project, revision_id)


@router.get("/{project_id}/revisions/{revision_id}/download")
async def download_presentation_revision(
    space_id: UUID,
    project_id: UUID,
    revision_id: UUID,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    project = await get_owned_project(db, project_id, user.id, space_id)
    revision = await get_revision(db, project.id, revision_id, completed=True)
    path = resolve_private_path(revision.pptx_path or "")
    return FileResponse(
        path,
        filename=f"{project.title}-v{revision.revision_number}.pptx",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


@router.get("/{project_id}/revisions/{revision_id}/preview/{page}", include_in_schema=False)
@router.get("/{project_id}/revisions/{revision_id}/previews/{page}")
async def preview_presentation_revision(
    space_id: UUID,
    project_id: UUID,
    revision_id: UUID,
    page: int,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    project = await get_owned_project(db, project_id, user.id, space_id)
    revision = await get_revision(db, project.id, revision_id, completed=True)
    page_entry = next(
        (item for item in (revision.preview_manifest or {}).get("pages", []) if int(item.get("page", 0)) == page),
        None,
    )
    if not page_entry:
        raise HTTPException(status_code=404, detail="预览页不存在")
    asset = await db.scalar(
        select(TeacherPresentationAsset).where(
            TeacherPresentationAsset.id == UUID(page_entry["asset_id"]),
            TeacherPresentationAsset.project_id == project.id,
            TeacherPresentationAsset.revision_id == revision.id,
            TeacherPresentationAsset.kind == PresentationAssetKind.PREVIEW,
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="预览页不存在")
    return FileResponse(resolve_private_path(asset.private_path), media_type=asset.mime_type or "image/png")


@router.post(
    "/{project_id}/revisions/{revision_id}/publish",
    response_model=PublicationResponse,
)
async def publish_presentation_revision(
    space_id: UUID,
    project_id: UUID,
    revision_id: UUID,
    payload: PublishRequest,
    user: User = Depends(require_course_teacher),
    db: AsyncSession = Depends(get_db),
) -> PublicationResponse:
    if payload.confirmed is not True:
        raise HTTPException(status_code=409, detail="发布前必须由教师显式确认")
    project = await get_owned_project(db, project_id, user.id, space_id)
    revision = await get_revision(db, project.id, revision_id, completed=True)
    publication = await publish_revision(
        db,
        project=project,
        revision=revision,
        publisher_user_id=user.id,
        title=payload.title,
    )
    return PublicationResponse(
        publication_id=publication.id,
        document_id=publication.document_id,
        revision_id=publication.revision_id,
        title=(payload.title or project.title),
        created_at=publication.created_at,
    )
