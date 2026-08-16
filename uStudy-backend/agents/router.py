"""Agent 模块 API 路由"""

from typing import Annotated
from uuid import UUID

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from agents.exceptions import (
    DocumentNotReadyError,
    SpaceAccessDeniedError,
    SpaceNotFoundError,
    TaskNotFoundError,
)
from agents.schemas import (
    AgentTaskResponse,
    AgentTaskResultResponse,
    DocumentKnowledgeGraphGenerateRequest,
    KnowledgeGraphGenerateRequest,
    QuizGenerateRequest,
)
from agents.document_knowledge_graph_agent import DocumentKnowledgeGraphAgent
from agents.service import AgentService
from auth.dependencies import get_current_user
from chat.router import sse_generator
from db.database import AsyncSessionLocal, get_db
from db.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post(
    "/knowledge-graph",
    response_model=AgentTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="生成知识图谱（异步）",
    description="启动异步知识图谱生成任务。返回任务 ID，通过 GET /tasks/{task_id} 查询状态。",
)
async def generate_knowledge_graph(
    request: KnowledgeGraphGenerateRequest,
    space_id: Annotated[UUID, Query(description="学习空间 ID（必填）")],
    conversation_id: Annotated[
        UUID | None, Query(description="关联对话 ID（可选，用于 SSE 通知）")
    ] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentTaskResponse:
    """
    启动知识图谱生成任务

    - **space_id**: 必须传入已存在的学习空间 ID
    - **topic**: 学习主题
    - **user_preference**: 用户偏好（可选）

    返回 202 Accepted，包含任务 ID。
    """
    service = AgentService(db)

    try:
        return await service.create_knowledge_graph_task(
            user_id=user.id,
            space_id=space_id,
            request=request,
            conversation_id=conversation_id,
        )
    except SpaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SPACE_NOT_FOUND", "message": "学习空间不存在"},
        )
    except SpaceAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SPACE_ACCESS_DENIED", "message": "无权访问该学习空间"},
        )


@router.post(
    "/quiz",
    response_model=AgentTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="生成测试题（异步）",
    description="启动异步测试题生成任务。返回任务 ID，通过 GET /tasks/{task_id} 查询状态。",
)
async def generate_quiz(
    request: QuizGenerateRequest,
    space_id: Annotated[UUID, Query(description="学习空间 ID（必填）")],
    conversation_id: Annotated[
        UUID | None, Query(description="关联对话 ID（可选）")
    ] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentTaskResponse:
    """
    启动测试题生成任务

    - **space_id**: 必须传入已存在的学习空间 ID
    - **topic**: 测试主题
    - **difficulty_level**: 难度级别 (easy/medium/hard)
    - **test_struct**: 题目结构配置

    返回 202 Accepted，包含任务 ID。
    """
    service = AgentService(db)

    try:
        return await service.create_quiz_task(
            user_id=user.id,
            space_id=space_id,
            request=request,
            conversation_id=conversation_id,
        )
    except SpaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SPACE_NOT_FOUND", "message": "学习空间不存在"},
        )
    except SpaceAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SPACE_ACCESS_DENIED", "message": "无权访问该学习空间"},
        )


@router.get(
    "/tasks/{task_id}",
    response_model=AgentTaskResultResponse,
    summary="查询任务状态",
    description="获取异步任务的执行状态和结果。",
)
async def get_task_status(
    task_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentTaskResultResponse:
    """
    查询任务状态

    - **task_id**: 任务 ID

    返回任务状态和结果（如果已完成）。
    """
    service = AgentService(db)

    try:
        return await service.get_task_status(user.id, task_id)
    except TaskNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TASK_NOT_FOUND", "message": "任务不存在"},
        )


@router.post(
    "/expand-node",
    response_model=AgentTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="扩展知识图谱节点（异步）",
    description="为指定节点生成 3-5 个子节点，异步执行。返回任务 ID，通过 GET /tasks/{task_id} 查询状态。",
)
async def expand_node(
    space_id: Annotated[UUID, Query(description="学习空间 ID")],
    node_id: Annotated[UUID, Query(description="目标节点 ID")],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentTaskResponse:
    """
    启动节点扩展任务

    - **space_id**: 学习空间 ID
    - **node_id**: 要扩展的节点 ID

    返回 202 Accepted，包含任务 ID。
    """
    service = AgentService(db)

    try:
        return await service.create_expand_node_task(
            user_id=user.id,
            space_id=space_id,
            node_id=node_id,
        )
    except SpaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SPACE_NOT_FOUND", "message": "学习空间不存在"},
        )
    except SpaceAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SPACE_ACCESS_DENIED", "message": "无权访问该学习空间"},
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NODE_NOT_FOUND", "message": str(e)},
        )


@router.post(
    "/knowledge-graph-from-documents",
    response_model=AgentTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="从文档生成知识图谱（异步）",
    description="从已上传并处理完成的文档中提取知识关系，生成知识图谱。",
)
async def generate_knowledge_graph_from_documents(
    request: DocumentKnowledgeGraphGenerateRequest,
    space_id: Annotated[UUID, Query(description="学习空间 ID")],
    conversation_id: Annotated[
        UUID | None, Query(description="关联对话 ID（可选）")
    ] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgentTaskResponse:
    """
    从文档生成知识图谱

    - **space_id**: 学习空间 ID
    - **document_ids**: 文档 ID 列表（必须已处理完成）
    - **user_preference**: 用户偏好（可选）

    返回 202 Accepted，包含任务 ID。
    """
    service = AgentService(db)

    try:
        return await service.create_document_knowledge_graph_task(
            user_id=user.id,
            space_id=space_id,
            request=request,
            conversation_id=conversation_id,
        )
    except SpaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SPACE_NOT_FOUND", "message": "学习空间不存在"},
        )
    except SpaceAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "SPACE_ACCESS_DENIED", "message": "无权访问该学习空间"},
        )
    except DocumentNotReadyError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "DOCUMENTS_NOT_READY", "message": str(e)},
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_DOCUMENTS", "message": str(e)},
        )


@router.post(
    "/knowledge-graph-from-documents/stream",
    summary="从文档流式生成知识图谱（SSE）",
    description="实时流式生成知识图谱，返回 SSE 事件流。Phase 1 发送提取进度，Phase 2 流式输出图谱节点。",
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream_knowledge_graph_from_documents(
    request: DocumentKnowledgeGraphGenerateRequest,
    space_id: Annotated[UUID, Query(description="学习空间 ID")],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    从文档流式生成知识图谱（SSE）

    事件类型：
    - phase: 阶段切换 {phase, total_chunks?}
    - progress: 提取进度 {completed, total}
    - kg_delta: LLM 增量文本 {content}
    - kg_node: 解析到节点 {label, level, parent?}
    - kg_edge: 解析到边 {source, target, type}
    - done: 完成 {node_count, edge_count}
    - error: 出错 {message}
    """
    # 准备阶段：验证权限（使用 FastAPI 的 DB session）
    from spaces.authorization import verify_space_access, SpaceNotFoundError as _NotFound, SpaceAccessDeniedError as _Denied
    try:
        await verify_space_access(db, space_id, user.id)
    except _NotFound:
        raise HTTPException(status_code=404, detail={"code": "SPACE_NOT_FOUND", "message": "学习空间不存在"})
    except _Denied:
        raise HTTPException(status_code=403, detail={"code": "SPACE_ACCESS_DENIED", "message": "无权访问该学习空间"})

    # 将参数提取为局部变量，供内部生成器使用
    document_ids = request.document_ids
    user_preference = request.user_preference
    user_id = user.id

    async def event_generator():
        """SSE 事件生成器，在独立 session 中运行"""
        async with AsyncSessionLocal() as session:
            try:
                agent = DocumentKnowledgeGraphAgent(session)
                async for event in agent.stream_generate(
                    user_id=user_id,
                    space_id=space_id,
                    document_ids=document_ids,
                    user_preference=user_preference,
                ):
                    yield {
                        "event": event["event"],
                        "data": json.dumps(event["data"], ensure_ascii=False),
                    }
            except DocumentNotReadyError as e:
                yield {
                    "event": "error",
                    "data": json.dumps({"message": str(e), "code": "DOCUMENTS_NOT_READY"}, ensure_ascii=False),
                }
            except (SpaceNotFoundError, SpaceAccessDeniedError) as e:
                yield {
                    "event": "error",
                    "data": json.dumps({"message": str(e)}, ensure_ascii=False),
                }
            except Exception as e:
                logger.error("流式知识图谱生成失败: %s", e, exc_info=True)
                yield {
                    "event": "error",
                    "data": json.dumps({"message": "生成失败，请重试"}, ensure_ascii=False),
                }

    return StreamingResponse(
        sse_generator(event_generator()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
