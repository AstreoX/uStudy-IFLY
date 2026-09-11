"""Internal, capability-scoped API exposed only to sandbox agent containers."""

from __future__ import annotations

import json
import logging
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.llm.client import LLMClient
from agents.llm.stream_driver import stream_tool_completion
from config import get_settings
from db.database import get_db
from db.models import (
    PresentationAssetKind,
    TeacherPresentationAsset,
    TeacherPresentationEvent,
    TeacherPresentationProject,
    TeacherPresentationRevision,
    TeacherPresentationRun,
)
from rag.vlm_processor import VLMProcessor
from teacher.presentations.schemas import (
    GatewayEvent,
    GatewayEventBatch,
    GatewayLLMRequest,
    GatewayToolRequest,
)
from teacher.presentations.service import (
    append_event,
    execute_capability_tool,
    resolve_private_path,
    save_gateway_artifact,
    verify_capability,
)
from usage.metering import UsageContext
from usage.models import UsageType

router = APIRouter(prefix="/api/internal/presentation-agent/runs", tags=["presentation-agent-internal"])
bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def _presentation_llm_client(
    *, request: GatewayLLMRequest, context: UsageContext
) -> LLMClient:
    return LLMClient(
        model_override=request.model or get_settings().presentation_llm_model,
        usage_context=context,
    )


async def capability_scope(
    run_id: UUID,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: AsyncSession = Depends(get_db),
    x_presentation_run: str | None = Header(None),
    x_presentation_project: str | None = Header(None),
) -> tuple[TeacherPresentationRun, TeacherPresentationProject]:
    return await verify_capability(
        db,
        run_id=run_id,
        token=credentials.credentials if credentials else "",
        header_run_id=x_presentation_run,
        header_project_id=x_presentation_project,
    )


_EVENT_MAP = {
    "started": "run_started",
    "text": "text_delta",
    "completed": "presentation_ready",
    "failed": "error",
    "blocked": "error",
}


@router.get("/{run_id}/state")
async def get_run_state(
    run_id: UUID,
    scope: tuple[TeacherPresentationRun, TeacherPresentationProject] = Depends(capability_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    run, _ = scope
    maximum = await db.scalar(
        select(func.max(TeacherPresentationEvent.sequence)).where(
            TeacherPresentationEvent.run_id == run.id
        )
    )
    return {
        "run_id": str(run.id),
        "status": run.status.value,
        "attempt": run.attempt_count,
        "last_sequence": int(maximum or 0),
    }


@router.post("/{run_id}/events", status_code=202)
async def receive_event(
    run_id: UUID,
    event: GatewayEvent,
    scope: tuple[TeacherPresentationRun, TeacherPresentationProject] = Depends(capability_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    run, project = scope
    event_type = _EVENT_MAP.get(event.type, event.type)
    event_payload = dict(event.payload or event.data)
    if event.type in {"skill_loaded", "sources_ready", "checkpoint", "warning"}:
        event_type = "presentation_progress"
        event_payload = {"stage": event.type, **event_payload}
    stored = await append_event(
        db,
        run=run,
        project=project,
        sequence=event.sequence,
        event_type=event_type,
        payload=event_payload,
    )
    return {"accepted": True, "event_id": str(stored.id)}


@router.post("/{run_id}/events/batch", status_code=202)
async def receive_event_batch(
    run_id: UUID,
    batch: GatewayEventBatch,
    scope: tuple[TeacherPresentationRun, TeacherPresentationProject] = Depends(capability_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Persist an ordered delta batch in one transaction."""

    run, project = scope
    stored = []
    for item in batch.events:
        event_type = _EVENT_MAP.get(item.type, item.type)
        event_payload = dict(item.payload or item.data)
        if item.type in {"skill_loaded", "sources_ready", "checkpoint", "warning"}:
            event_type = "presentation_progress"
            event_payload = {"stage": item.type, **event_payload}
        stored.append(
            await append_event(
                db,
                run=run,
                project=project,
                sequence=item.sequence,
                event_type=event_type,
                payload=event_payload,
                commit=False,
            )
        )
    await db.flush()
    await db.commit()
    return {"accepted": True, "event_ids": [str(item.id) for item in stored]}


@router.post("/{run_id}/tools/{tool_name}")
async def execute_tool(
    run_id: UUID,
    tool_name: str,
    request: GatewayToolRequest,
    scope: tuple[TeacherPresentationRun, TeacherPresentationProject] = Depends(capability_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    run, project = scope
    return await execute_capability_tool(
        db, run=run, project=project, tool_name=tool_name, arguments=request.arguments
    )


@router.post("/{run_id}/llm")
async def proxy_llm(
    run_id: UUID,
    request: GatewayLLMRequest,
    scope: tuple[TeacherPresentationRun, TeacherPresentationProject] = Depends(capability_scope),
) -> dict:
    run, project = scope
    context = UsageContext(
        user_id=run.user_id,
        usage_type=UsageType.AGENT_LLM,
        source_module="teacher_presentations",
        source_operation="sandbox_agent_llm",
        billable=True,
        space_id=run.space_id,
        conversation_id=project.conversation_id,
        metadata={"run_id": str(run.id), "project_id": str(project.id)},
    )
    result = await _presentation_llm_client(request=request, context=context).complete_with_tools(
        messages=request.messages,
        tools=request.tools,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        idempotency_key=f"presentation:{run.id}:{len(request.messages)}",
    )
    usage = None
    if result.usage:
        usage = {
            "prompt_tokens": result.usage.prompt_tokens,
            "completion_tokens": result.usage.completion_tokens,
            "total_tokens": result.usage.total_tokens,
        }
    return {
        "message": {
            "role": "assistant",
            "content": result.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in result.tool_calls
            ],
        },
        "finish_reason": result.finish_reason,
        "usage": usage,
    }


@router.post("/{run_id}/llm/stream")
async def proxy_llm_stream(
    run_id: UUID,
    request: GatewayLLMRequest,
    scope: tuple[TeacherPresentationRun, TeacherPresentationProject] = Depends(capability_scope),
) -> StreamingResponse:
    """Proxy the canonical main-chat LLM stream to the sandbox as NDJSON."""

    run, project = scope
    context = UsageContext(
        user_id=run.user_id,
        usage_type=UsageType.AGENT_LLM,
        source_module="teacher_presentations",
        source_operation="sandbox_agent_llm_stream",
        billable=True,
        space_id=run.space_id,
        conversation_id=project.conversation_id,
        metadata={"run_id": str(run.id), "project_id": str(project.id)},
    )

    async def generate():
        try:
            async for event in stream_tool_completion(
                _presentation_llm_client(request=request, context=context),
                messages=request.messages,
                tools=request.tools,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                enable_thinking=request.enable_thinking,
                usage_context=context,
                idempotency_key=f"presentation:{run.id}:{len(request.messages)}",
            ):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as exc:  # transport has already started; report in-band
            logger.exception("Presentation LLM stream failed for run %s", run.id)
            status_code = None
            provider_code = None
            detail = str(exc).strip() or exc.__class__.__name__
            if isinstance(exc, httpx.HTTPStatusError):
                status_code = exc.response.status_code
                try:
                    provider_error = (exc.response.json().get("error") or {})
                except (ValueError, AttributeError):
                    provider_error = {}
                if isinstance(provider_error, dict):
                    provider_code = str(provider_error.get("code") or "") or None
                    detail = str(provider_error.get("message") or detail)
            retryable = status_code is None or status_code >= 500 or status_code == 429
            if provider_code == "Arrearage":
                detail = "Qwen 模型服务账户欠费，请恢复百炼账户状态后再继续任务"
                retryable = False
            yield json.dumps(
                {
                    "type": "error",
                    "message": detail,
                    "error_type": exc.__class__.__name__,
                    "stage": "llm_stream",
                    "status_code": status_code,
                    "provider_code": provider_code,
                    "retryable": retryable,
                },
                ensure_ascii=False,
            ) + "\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{run_id}/sources")
async def list_sources(
    run_id: UUID,
    scope: tuple[TeacherPresentationRun, TeacherPresentationProject] = Depends(capability_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    run, project = scope
    revision = await db.get(TeacherPresentationRevision, run.revision_id)
    selected_ids = [UUID(item) for item in (revision.manifest or {}).get("source_ids", [])]
    source_filter = TeacherPresentationAsset.id.in_(selected_ids)
    assets = list(
        (
            await db.scalars(
                select(TeacherPresentationAsset)
                .where(
                    TeacherPresentationAsset.project_id == project.id,
                    source_filter,
                    TeacherPresentationAsset.kind.in_(
                        [PresentationAssetKind.SOURCE, PresentationAssetKind.TEMPLATE]
                    ),
                )
                .order_by(TeacherPresentationAsset.created_at)
            )
        ).all()
    )
    return {
        "items": [
            {
                "id": str(asset.id),
                "kind": asset.kind.value,
                "filename": asset.filename,
                "mime_type": asset.mime_type,
                "file_size": asset.file_size,
                "download_url": f"sources/{asset.id}",
            }
            for asset in assets
        ]
    }


@router.get("/{run_id}/sources/{asset_id}")
async def download_source(
    run_id: UUID,
    asset_id: UUID,
    scope: tuple[TeacherPresentationRun, TeacherPresentationProject] = Depends(capability_scope),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    run, project = scope
    revision = await db.get(TeacherPresentationRevision, run.revision_id)
    selected_ids = [UUID(item) for item in (revision.manifest or {}).get("source_ids", [])]
    asset = await db.scalar(
        select(TeacherPresentationAsset).where(
            TeacherPresentationAsset.id == asset_id,
            TeacherPresentationAsset.id.in_(selected_ids),
            TeacherPresentationAsset.project_id == project.id,
            TeacherPresentationAsset.kind.in_(
                [PresentationAssetKind.SOURCE, PresentationAssetKind.TEMPLATE]
            ),
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="source 不存在")
    path = resolve_private_path(asset.private_path)
    return FileResponse(path, filename=asset.filename, media_type=asset.mime_type)


@router.get("/{run_id}/assets/{asset_id}")
async def download_generated_asset(
    run_id: UUID,
    asset_id: UUID,
    scope: tuple[TeacherPresentationRun, TeacherPresentationProject] = Depends(capability_scope),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    run, project = scope
    asset = await db.scalar(
        select(TeacherPresentationAsset).where(
            TeacherPresentationAsset.id == asset_id,
            TeacherPresentationAsset.project_id == project.id,
            TeacherPresentationAsset.revision_id == run.revision_id,
            TeacherPresentationAsset.kind == PresentationAssetKind.GENERATED_IMAGE,
        )
    )
    if asset is None:
        raise HTTPException(status_code=404, detail="asset 不存在")
    path = resolve_private_path(asset.private_path)
    return FileResponse(path, filename=asset.filename, media_type=asset.mime_type)


@router.post("/{run_id}/artifacts", status_code=201)
async def upload_artifact(
    run_id: UUID,
    kind: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    metadata: Annotated[str | None, Form()] = None,
    scope: tuple[TeacherPresentationRun, TeacherPresentationProject] = Depends(capability_scope),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        asset_kind = PresentationAssetKind(kind)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="artifact kind 无效") from exc
    if asset_kind not in {
        PresentationAssetKind.PPTX,
        PresentationAssetKind.PREVIEW,
        PresentationAssetKind.GENERATED_IMAGE,
    }:
        raise HTTPException(status_code=422, detail="sandbox 不允许上传该类 asset")
    try:
        parsed_metadata = json.loads(metadata) if metadata else None
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="metadata 必须是 JSON") from exc
    if parsed_metadata is not None and not isinstance(parsed_metadata, dict):
        raise HTTPException(status_code=422, detail="metadata 必须是 JSON object")
    run, project = scope
    asset = await save_gateway_artifact(
        db,
        run=run,
        project=project,
        upload=file,
        kind=asset_kind,
        metadata=parsed_metadata,
    )
    return {"asset_id": str(asset.id), "kind": asset.kind.value, "file_size": asset.file_size}


@router.post("/{run_id}/visual-inspections")
async def inspect_rendered_slide(
    run_id: UUID,
    file: Annotated[UploadFile, File()],
    context: Annotated[str, Form()] = "",
    scope: tuple[TeacherPresentationRun, TeacherPresentationProject] = Depends(capability_scope),
) -> dict:
    run, project = scope
    image = await file.read()
    await file.close()
    if not image or len(image) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="渲染图必须在 8 MB 以内")
    if image[:8] != b"\x89PNG\r\n\x1a\n" and image[:2] != b"\xff\xd8":
        raise HTTPException(status_code=422, detail="视觉检查仅支持 PNG 或 JPEG")
    usage_context = UsageContext(
        user_id=run.user_id,
        usage_type=UsageType.AGENT_LLM,
        source_module="teacher_presentations",
        source_operation="slide_visual_inspection",
        billable=True,
        space_id=run.space_id,
        conversation_id=project.conversation_id,
        metadata={"run_id": str(run.id), "project_id": str(project.id)},
    )
    try:
        return await VLMProcessor(usage_context=usage_context).inspect_presentation_slide(
            image, context=context
        )
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        logger.warning(
            "Presentation visual inspection provider rejected run=%s status=%s",
            run.id,
            status_code,
        )
        return {
            "ok": False,
            "passed": False,
            "error_type": "VLMProviderError",
            "error": f"Qwen visual inspection provider returned HTTP {status_code}",
            "retryable": status_code >= 500 or status_code == 429,
            "issues": [],
        }
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        logger.warning("Presentation visual inspection transport failed: %s", exc)
        return {
            "ok": False,
            "passed": False,
            "error_type": exc.__class__.__name__,
            "error": str(exc).strip() or exc.__class__.__name__,
            "retryable": True,
            "issues": [],
        }
