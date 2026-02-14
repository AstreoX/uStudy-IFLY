"""Chat API Router"""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth.dependencies import get_current_user, require_active_subscription
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
    ClientToolResultRequest,
    ClientToolResultResponse,
)
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
from db.models import User
from spaces.service import SpaceService, SpaceNotFoundError as SpaceServiceNotFoundError, SpaceAccessDeniedError as SpaceServiceAccessDeniedError

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["chat"],
    dependencies=[Depends(require_active_subscription)],
)


async def sse_generator(event_generator):
    """
    Convert event generator to SSE format.

    Transforms dict events into SSE-formatted strings:
    event: {event_type}
    data: {json_data}
    """
    try:
        async for event in event_generator:
            event_type = event.get("event", "message")
            data = event.get("data", {})
            yield f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
    except Exception as e:
        logger.error(f"SSE generator error: {e}", exc_info=True)
        error_event = {
            "event": "error",
            "data": {"message": f"流式响应出错: {str(e)}"},
        }
        yield f"event: error\ndata: {json.dumps(error_event['data'], ensure_ascii=False)}\n\n"


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
    # Validate conversation AND space binding with a short-lived session
    async with get_scoped_session() as db:
        service = ChatService(db)
        try:
            await service.validate_conversation_access(
                user.id, conversation_id, require_space=True
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
        except SpaceRequiredError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "SPACE_REQUIRED", "message": str(e)},
            )
    # DB session released before SSE stream starts

    # Static method: manages its own short-lived DB sessions internally
    event_generator = ChatService.send_message(
        user.id,
        conversation_id,
        request.content,
        request.attachment_ids,
    )

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

    # Static method: manages its own short-lived DB sessions internally
    event_generator = ChatService.send_quick_chat_message(
        user.id,
        conversation_id,
        request.content,
        request.attachment_ids,
    )

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

    - `status`: "executed" 已执行 / "rejected" 已拒绝
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
    tool_result = await executor.execute(request.tool_name, request.arguments)

    return ToolConfirmResponse(
        status="executed",
        success=tool_result.success,
        data=tool_result.data,
        message=tool_result.message,
    )
