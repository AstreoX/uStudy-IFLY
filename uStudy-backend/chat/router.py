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
    ConversationResponse,
    ConversationDetailResponse,
    ConversationListResponse,
    ToolCallRequest,
    ToolCallExecuteResponse,
    ToolConfirmRequest,
    ToolConfirmResponse,
    QuickChatToolTaskStatusResponse,
    QuickChatToolTaskListResponse,
    QuickChatToolTaskBindResponse,
    ClientToolResultRequest,
    ClientToolResultResponse,
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
from chat.tools.learning_space_executor import LearningSpaceToolExecutor
from chat.tools.learning_space_tools import get_allowed_tool_names
from db.database import get_db, get_scoped_session
from db.models import Conversation, Message, MessageRole, User
from quota.service import check_daily_message_quota, check_model_access, get_effective_tier
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
        select(Conversation).where(Conversation.id == conversation_id)
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

    # Quota checks: model access (pure config) + daily message count (DB)
    check_model_access(user, request.model_id)
    async with get_scoped_session() as db:
        await check_daily_message_quota(db, user)

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
        await space_service.get_space(user.id, space_id)
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

    executor = GraphToolExecutor(space_id)
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


# ==================== Quick Chat Endpoints ====================


@router.post(
    "/quick-chat/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建快速对话",
    description="创建不绑定学习空间的快速对话",
)
async def create_quick_chat_conversation(
    request: CreateConversationRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Create a quick chat conversation (no space binding)"""
    service = ChatService(db)
    return await service.create_quick_chat_conversation(user.id, request.title)


@router.get(
    "/quick-chat/conversations",
    response_model=ConversationListResponse,
    summary="获取快速对话列表",
    description="获取当前用户的快速对话列表（space_id 为空的对话）",
)
async def list_quick_chat_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    """List quick chat conversations (no space binding)"""
    service = ChatService(db)
    return await service.list_quick_chat_conversations(user.id)


@router.post(
    "/quick-chat/conversations/{conversation_id}/messages",
    summary="快速对话发送消息（SSE）",
    description="""
    在快速对话中发送消息并接收流式响应。

    ## SSE 事件类型

    - `text_delta`: 增量文本内容 `{"content": "..."}`
    - `done`: 完成信号 `{"content": "完整响应"}`
    - `error`: 错误信号 `{"message": "..."}`

    ## 示例

    ```
    event: text_delta
    data: {"content": "你好，"}

    event: text_delta
    data: {"content": "我可以帮你解答问题。"}

    event: done
    data: {"content": "你好，我可以帮你解答问题。"}
    ```
    """,
    responses={
        200: {
            "description": "SSE 流式响应",
            "content": {"text/event-stream": {}},
        },
        403: {"description": "无权访问"},
        404: {"description": "对话不存在"},
    },
)
async def send_quick_chat_message(
    conversation_id: UUID,
    request: SendMessageRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Send message in quick chat mode (SSE streaming).
    Does NOT hold a DB session during streaming.
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

    # Quota checks: model access (pure config) + daily message count (DB)
    check_model_access(user, request.model_id)
    async with get_scoped_session() as db:
        await check_daily_message_quota(db, user)

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
    # DB session released before SSE stream starts

    logger.info(f"[Perf] QuickChat router validation: {(time.monotonic() - t_start)*1000:.0f}ms")

    # Static method: manages its own short-lived DB sessions internally
    event_generator = ChatService.send_quick_chat_message(
        user.id,
        conversation_id,
        request.content,
        request.attachment_ids,
        model_id=request.model_id,
        validated=True,
    )

    logger.info(f"[Perf] QuickChat router total: {(time.monotonic() - t_start)*1000:.0f}ms")
    return StreamingResponse(
        sse_generator(event_generator),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/quick-chat/conversations/{conversation_id}/tools/{tool_call_id}/confirm",
    response_model=ToolConfirmResponse,
    summary="确认或拒绝工具执行",
    description="""
    确认或拒绝需要用户确认的工具调用（如绑定学习空间、创建学习空间）。

    ## 请求参数

    - `tool_name`: 工具名称
    - `arguments`: 工具参数
    - `confirmed`: true 确认执行，false 拒绝执行

    ## 响应

    - `status`: "executed" 已执行 / "rejected" 已拒绝 / "accepted" 异步受理
    - `success`: 执行是否成功（仅当 status=executed）
    - `data`: 执行结果数据
    - `message`: 结果消息
    """,
)
async def confirm_tool_execution(
    conversation_id: UUID,
    tool_call_id: str,
    request: ToolConfirmRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ToolConfirmResponse:
    """Confirm or reject a pending tool execution in quick chat mode."""
    service = ChatService(db)

    # Validate conversation access
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

    # If user rejected, return immediately
    if not request.confirmed:
        return ToolConfirmResponse(
            status="rejected",
            success=None,
            data=None,
            message="用户取消了操作",
        )

    # Validate tool name against allowed list
    allowed_tools = get_allowed_tool_names()
    if request.tool_name not in allowed_tools:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TOOL", "message": "无效的工具名称"},
        )

    # Execute the tool
    executor = LearningSpaceToolExecutor(user.id, conversation_id)
    tool_result = await executor.execute(
        request.tool_name,
        request.arguments,
        tool_call_id=tool_call_id,
    )

    response_status = "executed"
    action = (
        tool_result.data.get("action")
        if isinstance(tool_result.data, dict)
        else None
    )
    if (
        request.tool_name == "create_learning_space"
        and action in {"async_create_learning_space", "existing_running_task"}
    ):
        response_status = "accepted"

    return ToolConfirmResponse(
        status=response_status,
        success=tool_result.success,
        data=tool_result.data,
        message=tool_result.message,
    )


@router.get(
    "/quick-chat/conversations/{conversation_id}/tools/tasks",
    response_model=QuickChatToolTaskListResponse,
    summary="获取快速对话工具任务列表",
    description="用于页面刷新/重开后恢复 create_learning_space 异步任务跟踪。",
)
async def list_quick_chat_tool_tasks(
    conversation_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuickChatToolTaskListResponse:
    """List async quick-chat create_learning_space tasks for current conversation."""
    service = ChatService(db)

    # Validate conversation access
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

    executor = LearningSpaceToolExecutor(user.id, conversation_id)
    tool_result = await executor.list_tool_tasks()

    return QuickChatToolTaskListResponse(
        success=tool_result.success,
        data=tool_result.data or {"tasks": [], "count": 0},
        message=tool_result.message,
    )


@router.get(
    "/quick-chat/conversations/{conversation_id}/tools/{tool_call_id}/status",
    response_model=QuickChatToolTaskStatusResponse,
    summary="获取快速对话工具任务状态",
    description="查询并同步指定 create_learning_space 异步任务状态（含阶段推进与失败原因）。",
)
async def get_quick_chat_tool_task_status(
    conversation_id: UUID,
    tool_call_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuickChatToolTaskStatusResponse:
    """Get async create-space task status by tool_call_id."""
    service = ChatService(db)

    # Validate conversation access
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

    executor = LearningSpaceToolExecutor(user.id, conversation_id)
    tool_result = await executor.get_tool_task_status(tool_call_id)

    return QuickChatToolTaskStatusResponse(
        success=tool_result.success,
        data=tool_result.data,
        message=tool_result.message,
    )


@router.post(
    "/quick-chat/conversations/{conversation_id}/tools/{tool_call_id}/bind",
    response_model=QuickChatToolTaskBindResponse,
    summary="绑定快速对话异步创建的学习空间",
    description="在知识图谱完成后执行会话绑定；失败时返回阶段化错误信息。",
)
async def bind_quick_chat_tool_task(
    conversation_id: UUID,
    tool_call_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuickChatToolTaskBindResponse:
    """Bind conversation to the space created by async create_learning_space task."""
    service = ChatService(db)

    # Validate conversation access
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

    executor = LearningSpaceToolExecutor(user.id, conversation_id)
    tool_result = await executor.bind_tool_task(tool_call_id)

    return QuickChatToolTaskBindResponse(
        success=tool_result.success,
        data=tool_result.data,
        message=tool_result.message,
    )
