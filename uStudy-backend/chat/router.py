"""Chat API Router"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user
from chat.schemas import (
    SendMessageRequest,
    CreateConversationRequest,
    UpdateConversationRequest,
    UpdateConversationTodoStatusRequest,
    ConversationResponse,
    ConversationDetailResponse,
    ConversationTodoListResponse,
    ConversationListResponse,
    ConversationSearchResponse,
    ToolCallRequest,
    ToolCallExecuteResponse,
    ClientToolResultRequest,
    ClientToolResultResponse,
    RollbackResponse,
    StopStreamResponse,
)
from chat.agent_todo_service import (
    AgentTodoService,
    ConversationTodoNotFoundError,
    ConversationTodoAccessDeniedError,
    AgentTodoItemNotFoundError,
)
from chat.models_config import get_available_models, validate_model_id
from chat.service import (
    ChatService,
    ConversationNotFoundError,
    ConversationAccessDeniedError,
    SpaceRequiredError,
    SpaceNotFoundError,
    SpaceAccessDeniedError,
)
from chat.tools.graph_tools import GraphToolExecutor
from chat.streaming_cache import get_streaming_state
from db.database import get_db, get_scoped_session
from db.models import Conversation, ConversationKind, Message, MessageRole, User
from quota.service import check_model_access, get_effective_tier
from spaces.service import SpaceService, SpaceNotFoundError as SpaceServiceNotFoundError, SpaceAccessDeniedError as SpaceServiceAccessDeniedError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["chat"],
)


@router.get(
    "/models",
    summary="获取可用模型列表",
    description="返回当前支持的 AI 模型列表",
)
async def list_models(
    user: User = Depends(get_current_user),
) -> list[dict]:
    """Return available AI models for the user's subscription tier."""
    tier = get_effective_tier(user)
    return get_available_models(tier=tier)


_STOP = object()


async def _safe_anext(ait):
    """Advance async iterator, returning _STOP on exhaustion."""
    try:
        return await ait.__anext__()
    except StopAsyncIteration:
        return _STOP


async def sse_generator(event_generator):
    """Convert event generator to SSE format with keepalive heartbeats.

    Sends an SSE comment (`: heartbeat`) every 15 seconds when idle to prevent
    network intermediaries / Android WebView from dropping the connection during
    long-running operations (e.g. waiting for client tool results, LLM calls).
    """
    HEARTBEAT_INTERVAL = 15  # seconds
    ait = event_generator.__aiter__()
    pending = asyncio.create_task(_safe_anext(ait))

    try:
        while True:
            done, _ = await asyncio.wait({pending}, timeout=HEARTBEAT_INTERVAL)

            if not done:
                # Idle timeout — send SSE comment as keepalive
                yield ": heartbeat\n\n"
                continue

            event = pending.result()
            if event is _STOP:
                break

            event_type = event.get("event", "message")
            data = event.get("data", {})
            yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

            pending = asyncio.create_task(_safe_anext(ait))
    except Exception as e:
        logger.error(f"SSE generator error: {e}", exc_info=True)
        yield f"event: error\ndata: {json.dumps({'message': f'流式响应出错: {str(e)}'}, ensure_ascii=False)}\n\n"
    finally:
        if not pending.done():
            pending.cancel()
            try:
                await pending
            except (asyncio.CancelledError, Exception):
                pass
        # Close the underlying async generator to release any held resources
        aclose = getattr(ait, 'aclose', None)
        if aclose is not None:
            try:
                await aclose()
            except Exception:
                pass


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="获取对话详情",
    description="获取对话及其所有消息",
)
async def get_conversation_detail(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    """Get conversation with messages"""
    service = ChatService(db)

    try:
        return await service.get_conversation_detail(user.id, conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "对话不存在"},
        )
    except ConversationAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCESS_DENIED", "message": "无权访问该对话"},
        )


@router.get(
    "/conversations/{conversation_id}/todos",
    response_model=ConversationTodoListResponse,
    summary="获取对话级 agent todo 列表",
    description="返回当前对话的完整 agent todo 列表",
)
async def get_conversation_todos(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationTodoListResponse:
    """Get the normalized agent todo list for a conversation."""
    service = AgentTodoService(db)

    try:
        payload = await service.get_todos(user.id, conversation_id)
        return ConversationTodoListResponse.model_validate(payload)
    except ConversationTodoNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "对话不存在"},
        )
    except ConversationTodoAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCESS_DENIED", "message": "无权访问该对话"},
        )


@router.patch(
    "/conversations/{conversation_id}/todos/{task_id}",
    response_model=ConversationTodoListResponse,
    summary="更新对话级 agent todo 完成状态",
    description="允许用户手动切换某个对话级 agent todo 的完成状态",
)
async def update_conversation_todo_status(
    conversation_id: UUID,
    task_id: str,
    payload: UpdateConversationTodoStatusRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationTodoListResponse:
    """Update the completion state of a conversation todo item."""
    service = AgentTodoService(db)

    try:
        result = await service.set_todo_completion(
            user.id,
            conversation_id,
            task_id,
            payload.completed,
        )
        return ConversationTodoListResponse.model_validate(result)
    except ConversationTodoNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "对话不存在"},
        )
    except ConversationTodoAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCESS_DENIED", "message": "无权访问该对话"},
        )
    except AgentTodoItemNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TODO_NOT_FOUND", "message": "待办不存在"},
        )


@router.get(
    "/conversations/{conversation_id}/reply-status",
    summary="检查AI回复状态",
    description="轻量级端点，供前端后台轮询检查 AI 是否已完成回复",
)
async def check_reply_status(
    conversation_id: UUID,
    after: float = Query(..., ge=0, le=4102444800.0, description="用户消息发送时间戳(Unix seconds)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check if AI has replied after a given timestamp. For background polling."""
    # Validate ownership
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.kind == ConversationKind.LEARNING,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv or conv.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "对话不存在"},
        )

    # Check for assistant message after timestamp
    after_dt = datetime.fromtimestamp(after, tz=timezone.utc).replace(tzinfo=None)
    result = await db.execute(
        select(Message.content)
        .where(
            Message.conversation_id == conversation_id,
            Message.role == MessageRole.ASSISTANT,
            Message.created_at > after_dt,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    row = result.first()
    if row:
        preview = (row[0] or "")[:80]
        return {"has_reply": True, "preview": preview}
    return {"has_reply": False, "preview": ""}


@router.get(
    "/conversations/{conversation_id}/streaming-status",
    summary="查询流式传输状态",
    description="查询对话是否有正在进行的AI流式回复，用于断连后恢复",
)
async def get_streaming_status(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Check if there's an active streaming response for this conversation.

    Returns:
        - is_streaming: True if AI is currently generating a response
        - is_stopped: True if AI generation was explicitly stopped by the user
        - partial_content: Content generated so far (if streaming)
        - partial_thinking: Thinking content generated so far (if streaming)
        - tool_calls: Tool calls made so far
        - updated_at: Last update timestamp
    """
    # Validate ownership
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.kind == ConversationKind.LEARNING,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv or conv.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "对话不存在"},
        )

    # Get streaming state from Redis cache
    state = await get_streaming_state(str(conversation_id))

    if state is None:
        return {
            "is_streaming": False,
            "is_stopped": False,
            "stop_reason": None,
            "partial_content": None,
            "partial_thinking": None,
            "tool_calls": [],
            "updated_at": None,
        }

    return {
        "is_streaming": not state.is_complete and not state.is_stopped,
        "is_stopped": state.is_stopped,
        "stop_reason": state.stop_reason,
        "partial_content": state.content or None,
        "partial_thinking": state.thinking or None,
        "tool_calls": state.tool_calls,
        "updated_at": state.updated_at,
    }


@router.post(
    "/conversations/{conversation_id}/stop-stream",
    response_model=StopStreamResponse,
    summary="终止当前 AI 回复",
    description="用户主动停止当前会话中的 AI 流式回复，保留已生成的 partial content。",
)
async def stop_stream(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StopStreamResponse:
    """Stop an in-flight AI streaming response for the conversation."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.kind == ConversationKind.LEARNING,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv or conv.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "对话不存在"},
        )

    payload = await ChatService.stop_stream(conversation_id)
    return StopStreamResponse(**payload)


@router.get(
    "/conversations/{conversation_id}/resume-stream",
    summary="断点续传流式响应",
    description="""
    从断点继续接收流式内容。

    ## 使用场景

    当客户端在接收流式响应过程中断连后：
    1. 先调用 `/streaming-status` 检查是否仍在流式传输
    2. 如果 `is_streaming=true`，调用此端点从断点继续

    ## 参数

    - `offset`: 已接收的字符数，从此位置继续

    ## SSE 事件类型

    与 `/messages` 端点相同
    """,
)
async def resume_stream(
    conversation_id: UUID,
    offset: int = Query(0, ge=0, description="已接收的字符数"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resume streaming from a specific offset after disconnection."""
    # Validate ownership
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.kind == ConversationKind.LEARNING,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv or conv.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "对话不存在"},
        )

    async def resume_generator():
        last_content_len = offset
        max_iterations = 1800  # Max 3 minutes at 100ms interval

        for _ in range(max_iterations):
            state = await get_streaming_state(str(conversation_id))

            if state is None:
                # Cache expired or doesn't exist - stream is done
                yield {
                    "event": "done",
                    "data": {"content": "", "resumed": True, "cache_expired": True},
                }
                break

            # Send incremental content if available
            if len(state.content) > last_content_len:
                delta = state.content[last_content_len:]
                yield {
                    "event": "text_delta",
                    "data": {"content": delta},
                }
                last_content_len = len(state.content)

            if state.is_stopped:
                yield {
                    "event": "done",
                    "data": {
                        "content": state.content,
                        "resumed": True,
                        "response_status": "stopped",
                        "stopped": True,
                    },
                }
                break

            if state.is_complete:
                yield {
                    "event": "done",
                    "data": {
                        "content": state.content,
                        "resumed": True,
                        "response_status": "completed",
                    },
                }
                break

            # Wait for next update
            await asyncio.sleep(0.1)
        else:
            # Timeout - should not normally happen
            yield {
                "event": "error",
                "data": {"message": "Resume timeout"},
            }

    return StreamingResponse(
        sse_generator(resume_generator()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    summary="发送消息（SSE流式响应）",
    description="""
    发送消息并接收流式响应。

    ## SSE 事件类型

    - `text_delta`: 增量文本内容 `{"content": "..."}`
    - `tool_call`: 工具调用状态 `{"id": "...", "tool": "...", "status": "running|done", ...}`
    - `done`: 完成信号 `{"content": "完整响应"}`
    - `error`: 错误信号 `{"message": "..."}`

    ## 示例

    ```
    event: text_delta
    data: {"content": "好的，让我"}

    event: tool_call
    data: {"id": "call_123", "tool": "get_graph_overview", "status": "running"}

    event: tool_call
    data: {"id": "call_123", "tool": "get_graph_overview", "status": "done", "success": true, "result": {...}}

    event: text_delta
    data: {"content": "来查看一下你的知识图谱..."}

    event: done
    data: {"content": "好的，让我来查看一下你的知识图谱..."}
    ```
    """,
    responses={
        200: {
            "description": "SSE 流式响应",
            "content": {"text/event-stream": {}},
        },
        403: {"description": "无权访问"},
        404: {"description": "对话不存在"},
        422: {"description": "请求参数错误"},
    },
)
async def send_message(
    conversation_id: UUID,
    request: SendMessageRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Send message and receive SSE streaming response.

    Requires conversation to be bound to a learning space.
    Does NOT hold a DB session during SSE streaming.
    Validation uses a short-lived session; the streaming method manages its own sessions.
    """
    t_start = time.monotonic()

    # Validate model_id early (before entering SSE stream)
    if request.model_id is not None and not validate_model_id(request.model_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "INVALID_MODEL",
                "message": f"无效的模型ID: {request.model_id}",
                "available_models": [m["id"] for m in get_available_models()],
            },
        )

    # Quota checks: model access preflight
    check_model_access(user, request.model_id)

    # Validate conversation AND space binding with a short-lived session
    validated_space_id = None
    async with get_scoped_session() as db:
        service = ChatService(db)
        try:
            conv = await service.validate_conversation_access(
                user.id, conversation_id, require_space=True
            )
            validated_space_id = conv.space_id
        except ConversationNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "CONVERSATION_NOT_FOUND", "message": "对话不存在"},
            )
        except ConversationAccessDeniedError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ACCESS_DENIED", "message": "无权访问该对话"},
            )
        except SpaceRequiredError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "SPACE_REQUIRED", "message": str(e)},
            )
    # DB session released before SSE stream starts

    logger.info(f"[Perf] Router validation: {(time.monotonic() - t_start)*1000:.0f}ms")

    # Static method: manages its own short-lived DB sessions internally
    event_generator = ChatService.send_message(
        user.id,
        conversation_id,
        request.content,
        request.attachment_ids,
        model_id=request.model_id,
        validated_space_id=validated_space_id,
        panel_screenshot=request.panel_screenshot,
        thinking=request.thinking,
    )

    logger.info(f"[Perf] Router total: {(time.monotonic() - t_start)*1000:.0f}ms")
    return StreamingResponse(
        sse_generator(event_generator),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.post(
    "/conversations/{conversation_id}/tool-result",
    response_model=ClientToolResultResponse,
    summary="提交客户端工具执行结果",
    description="""
    前端执行客户端工具（如 Android 日历操作）后，将结果回传给后端。
    后端 SSE 流会在收到结果后继续 LLM 循环。
    """,
)
async def submit_client_tool_result(
    conversation_id: UUID,
    request: ClientToolResultRequest,
    user: User = Depends(get_current_user),
) -> ClientToolResultResponse:
    """Submit client-side tool execution result."""
    from chat.tools.client_tool_bridge import submit_tool_result

    # Validate conversation access with a short-lived session
    async with get_scoped_session() as db:
        service = ChatService(db)
        try:
            await service.validate_conversation_access(
                user.id, conversation_id, require_space=False
            )
        except ConversationNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "CONVERSATION_NOT_FOUND", "message": "对话不存在"},
            )
        except ConversationAccessDeniedError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ACCESS_DENIED", "message": "无权访问该对话"},
            )

    found = await submit_tool_result(
        tool_call_id=request.tool_call_id,
        success=request.success,
        result=request.result,
        error=request.error,
        conversation_id=conversation_id,
    )

    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "TOOL_REQUEST_NOT_FOUND",
                "message": "未找到对应的待处理工具请求",
            },
        )

    return ClientToolResultResponse(received=True, message="结果已接收")


@router.post(
    "/spaces/{space_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建对话",
    description="为学习空间创建新对话",
)
async def create_conversation(
    space_id: UUID,
    request: CreateConversationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Create a new conversation for a learning space"""
    service = ChatService(db)

    try:
        return await service.create_conversation(user.id, space_id, request.title)
    except SpaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SPACE_NOT_FOUND", "message": "学习空间不存在"},
        )
    except SpaceAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCESS_DENIED", "message": "无权访问该学习空间"},
        )


@router.get(
    "/spaces/{space_id}/conversations",
    response_model=ConversationListResponse,
    summary="获取空间对话列表",
    description="获取学习空间内所有对话",
)
async def list_conversations(
    space_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    """List all conversations for a learning space"""
    service = ChatService(db)

    try:
        return await service.list_conversations(user.id, space_id)
    except SpaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SPACE_NOT_FOUND", "message": "学习空间不存在"},
        )
    except SpaceAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCESS_DENIED", "message": "无权访问该学习空间"},
        )


@router.get(
    "/spaces/{space_id}/conversations/search",
    response_model=ConversationSearchResponse,
    summary="搜索空间对话历史",
    description="""
    在指定学习空间内搜索对话历史。

    ## 搜索范围

    - `scope=title`：仅搜索对话标题
    - `scope=content`：仅搜索消息正文
    - `scope=all`（默认）：标题 OR 消息正文均匹配

    ## 返回

    每条对话包含 `matching_messages`（最多 3 条匹配消息片段），片段保留关键词上下文（最多 200 字符）。
    """,
)
async def search_conversations(
    space_id: UUID,
    q: str = Query(..., min_length=1, max_length=200, description="搜索关键词"),
    scope: str = Query("all", pattern="^(title|content|all)$", description="搜索范围: title | content | all"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=50, description="每页条数（最大 50）"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationSearchResponse:
    """Search conversations within a learning space by title and/or message content."""
    service = ChatService(db)

    try:
        return await service.search_conversations(
            user.id, space_id, q, scope=scope, page=page, page_size=page_size
        )
    except SpaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SPACE_NOT_FOUND", "message": "学习空间不存在"},
        )
    except SpaceAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCESS_DENIED", "message": "无权访问该学习空间"},
        )


@router.post(
    "/spaces/{space_id}/tools/execute",
    response_model=ToolCallExecuteResponse,
    summary="执行知识图谱工具（调试）",
    description="用于调试工具调用，输入格式与 LLM tool_call 一致。",
)
async def execute_space_tool(
    space_id: UUID,
    request: ToolCallRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ToolCallExecuteResponse:
    """Execute a knowledge graph tool call and return raw tool output."""
    space_service = SpaceService(db)

    try:
        space = await space_service.get_space(user.id, space_id)
    except SpaceServiceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SPACE_NOT_FOUND", "message": "学习空间不存在"},
        )
    except SpaceServiceAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCESS_DENIED", "message": "无权访问该学习空间"},
        )

    raw_arguments = request.function.arguments
    if isinstance(raw_arguments, str):
        try:
            arguments = json.loads(raw_arguments) if raw_arguments.strip() else {}
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "INVALID_ARGUMENTS", "message": "arguments 不是合法 JSON 字符串"},
            )
    elif isinstance(raw_arguments, dict):
        arguments = raw_arguments
    else:
        arguments = {}

    is_owner = (space.user_id == user.id)
    if (space.is_collaborative or False) and not is_owner:
        from db.models import SpaceMember
        member_result = await db.execute(
            select(SpaceMember.can_edit_graph).where(
                SpaceMember.space_id == space_id,
                SpaceMember.user_id == user.id,
            )
        )
        can_edit_graph = member_result.scalar_one_or_none() or False
    else:
        can_edit_graph = True

    executor = GraphToolExecutor(
        space_id,
        user_id=user.id,
        is_collaborative=space.is_collaborative or False,
        can_edit_graph=can_edit_graph,
    )
    tool_result = await executor.execute(request.function.name, arguments)
    raw_tool_output = json.dumps(tool_result.to_dict(), ensure_ascii=False)

    return ToolCallExecuteResponse(
        raw_tool_output=raw_tool_output,
        parsed=tool_result.to_dict(),
    )


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="更新对话",
    description="更新对话属性（如绑定到学习空间）",
)
async def update_conversation(
    conversation_id: UUID,
    request: UpdateConversationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Update conversation properties (e.g., bind to learning space)"""
    service = ChatService(db)

    try:
        return await service.update_conversation(user.id, conversation_id, request)
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "对话不存在"},
        )
    except ConversationAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCESS_DENIED", "message": "无权访问该对话"},
        )
    except SpaceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SPACE_NOT_FOUND", "message": "学习空间不存在"},
        )
    except SpaceAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCESS_DENIED", "message": "无权访问该学习空间"},
        )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除对话",
    description="删除对话及其所有消息",
)
async def delete_conversation(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a conversation"""
    service = ChatService(db)

    try:
        await service.delete_conversation(user.id, conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "对话不存在"},
        )
    except ConversationAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCESS_DENIED", "message": "无权访问该对话"},
        )


@router.post(
    "/conversations/{conversation_id}/rollback",
    response_model=RollbackResponse,
    summary="回滚最后一轮对话",
    description="删除对话中最后一条用户消息及其后续的所有AI回复，用于消息编辑功能。",
)
async def rollback_last_message(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RollbackResponse:
    """Roll back the last user message round for editing."""
    service = ChatService(db)

    try:
        deleted_count = await service.rollback_last_message(user.id, conversation_id)
        return RollbackResponse(deleted_count=deleted_count)
    except ConversationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CONVERSATION_NOT_FOUND", "message": "对话不存在"},
        )
    except ConversationAccessDeniedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCESS_DENIED", "message": "无权访问该对话"},
        )
