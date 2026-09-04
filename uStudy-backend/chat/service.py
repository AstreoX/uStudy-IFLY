"""Chat Service - Conversation and Message Management"""

import asyncio
import base64
import logging
import time
from dataclasses import dataclass
from datetime import timezone
from pathlib import Path
from typing import Any, AsyncGenerator
from uuid import UUID

from sqlalchemy import select, delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from chat.models_config import get_max_output_tokens, get_model_id
from chat.orchestrator import LLMOrchestrator
from chat.streaming_cache import get_streaming_state, mark_streaming_stopped
from chat.title_generator import generate_title, fallback_title
from memory.extractor import MemoryExtractor
from chat.schemas import (
    MessageResponse,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationListResponse,
    ConversationSearchResponse,
    ConversationSearchItem,
    MessageSnippet,
    UpdateConversationRequest,
)
from config import get_settings
from db.database import get_scoped_session
from db.models import (
    AttachmentType,
    Conversation,
    ConversationKind,
    Message,
    MessageAttachment,
    MessageResponseStatus,
    MessageRole,
    Space,
    SpaceMember,
)
from experiment.course_catalog import is_managed_course

logger = logging.getLogger(__name__)


async def _resolve_space_graph_edit_permission(
    db: AsyncSession, space: Space, user_id: UUID
) -> bool:
    """Resolve graph-edit access without trusting a stale membership snapshot."""

    if space.user_id == user_id:
        return True
    if is_managed_course(space.id):
        return False
    if not space.is_collaborative:
        return False
    can_edit = await db.scalar(
        select(SpaceMember.can_edit_graph).where(
            SpaceMember.space_id == space.id,
            SpaceMember.user_id == user_id,
        )
    )
    return bool(can_edit)


def _extract_snippet(content: str, query: str, max_len: int = 200) -> str:
    """Extract a context snippet around the first occurrence of query in content."""
    idx = content.lower().find(query.lower())
    if idx == -1:
        return content[:max_len]
    start = max(0, idx - 60)
    end = min(len(content), idx + len(query) + 60)
    snippet = content[start:end]
    if start > 0:
        snippet = "\u2026" + snippet
    if end < len(content):
        snippet = snippet + "\u2026"
    return snippet


def _extract_tool_calls_from_context(llm_context: dict | None) -> list[dict] | None:
    """Extract tool calls from llm_context for frontend rendering."""
    if not llm_context:
        return None
    iterations = (llm_context.get("response") or {}).get("iterations") or []
    extracted = []
    for iteration in iterations:
        tc_list = iteration.get("tool_calls") or []
        tr_list = iteration.get("tool_results") or []
        results_map = {r["tool_call_id"]: r for r in tr_list if r.get("tool_call_id")}
        for tc in tc_list:
            tc_id = tc.get("id")
            result = results_map.get(tc_id, {})
            extracted.append({
                "id": tc_id,
                "tool": tc.get("name"),
                "arguments": tc.get("arguments"),
                "status": "done",
                "success": result.get("success"),
                "result": result.get("data"),
                "message": result.get("message"),
            })
    return extracted if extracted else None


def _extract_image_urls_from_llm_message(message: dict[str, Any]) -> list[str]:
    """Extract image URLs from an LLM-formatted multimodal message."""
    content = message.get("content")
    if not isinstance(content, list):
        return []

    image_urls: list[str] = []
    for part in content:
        if not isinstance(part, dict) or part.get("type") != "image_url":
            continue

        image_value = part.get("image_url")
        image_url = image_value.get("url") if isinstance(image_value, dict) else image_value
        if isinstance(image_url, str) and image_url:
            image_urls.append(image_url)

    return image_urls

# Context window limit - how many messages to include in LLM context
# DeepSeek V3 has 128K context window, so we can include more history
MAX_HISTORY_MESSAGES = 50


@dataclass
class ActiveStreamTask:
    """Bookkeeping for an active streaming generation task."""

    task: asyncio.Task


def _log_task_exception(task: asyncio.Task) -> None:
    """Done callback to log unhandled exceptions in background tasks."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error(f"Background chat task failed: {exc}", exc_info=exc)


async def _persist_assistant_message(
    conversation_id: UUID,
    content: str,
    llm_context: dict | None,
    citations: list[dict[str, Any]] | None,
    response_status: MessageResponseStatus,
    tool_calls: list[dict[str, Any]] | None = None,
) -> None:
    """Persist an assistant message with its final generation status."""
    if not content:
        return

    async with get_scoped_session() as save_db:
        assistant_message = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=content,
            llm_context=llm_context,
            tool_calls=tool_calls if tool_calls is not None else _extract_tool_calls_from_context(llm_context),
            citations=citations,
            response_status=response_status,
        )
        save_db.add(assistant_message)
        await save_db.commit()

def _encode_image_to_base64(attachment: MessageAttachment) -> str:
    """
    Encode image file to base64 data URI.

    Args:
        attachment: MessageAttachment object with file_url

    Returns:
        Base64 data URI (e.g., "data:image/webp;base64,...")
    """
    try:
        settings = get_settings()
        # Extract file path from URL
        # file_url format: http://localhost:8000/uploads/attachments/images/xxx.webp
        # We need to construct the actual file path
        url_path = attachment.file_url.split("/uploads/")[-1]
        file_path = Path(settings.upload_dir) / url_path

        # Read and encode image
        with open(file_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        return f"data:{attachment.mime_type};base64,{image_data}"
    except Exception as e:
        logger.error(
            f"Failed to encode image {attachment.file_url} to base64: {e}",
            exc_info=True,
        )
        # Fallback to URL (might not work but better than crashing)
        return attachment.file_url


def _build_llm_message_with_attachments(message: Message) -> dict[str, Any]:
    """
    Build LLM message with attachments in OpenRouter multimodal format.

    DEPRECATED: Use _build_llm_message_with_attachments_async instead.
    This sync version is kept for backward compatibility but doesn't support file content extraction.

    Args:
        message: Message object with attachments relationship loaded

    Returns:
        Message dict compatible with OpenRouter Vision API format
    """
    # If no attachments, return simple text format
    if not message.attachments:
        return {"role": message.role.value, "content": message.content}

    # With attachments, use multimodal format
    settings = get_settings()
    content_parts = []

    # 1. Add text part (if any)
    if message.content and message.content.strip():
        content_parts.append({"type": "text", "text": message.content})

    # 2. Add image parts
    for attachment in message.attachments:
        if attachment.attachment_type == AttachmentType.IMAGE:
            # Use base64 encoding or URL based on config
            if settings.use_base64_for_images:
                image_url = _encode_image_to_base64(attachment)
            else:
                # Use direct URL (requires public access)
                image_url = attachment.file_url

            content_parts.append(
                {"type": "image_url", "image_url": {"url": image_url}}
            )
        # FILE type attachments are not supported yet

    return {"role": message.role.value, "content": content_parts}


async def _build_llm_message_with_attachments_async(
    message: Message, db: AsyncSession
) -> dict[str, Any]:
    """
    Build LLM message with attachments in OpenRouter multimodal format (async version).

    This version supports:
    - Images: Base64 encoding or URL
    - Files: Text extraction from PDF, DOCX, TXT with caching

    Args:
        message: Message object with attachments relationship loaded
        db: Database session for caching extracted text

    Returns:
        Message dict compatible with OpenRouter Vision API format
    """
    # If no attachments, return simple text format
    if not message.attachments:
        return {"role": message.role.value, "content": message.content}

    settings = get_settings()
    content_parts = []
    file_contents = []

    # Process attachments
    for idx, attachment in enumerate(message.attachments, start=1):
        if attachment.attachment_type == AttachmentType.IMAGE:
            # Image handling (existing logic)
            if settings.use_base64_for_images:
                image_url = _encode_image_to_base64(attachment)
            else:
                image_url = attachment.file_url

            content_parts.append(
                {"type": "image_url", "image_url": {"url": image_url}}
            )

        elif attachment.attachment_type == AttachmentType.FILE:
            # File handling: extract text content
            extracted_text = attachment.extracted_text

            # If not cached, extract now
            if extracted_text is None and settings.attachment_cache_extracted_text:
                from chat.text_extractor import extract_text_from_attachment

                extracted_text, metadata = await extract_text_from_attachment(
                    attachment
                )

                # Cache to database
                attachment.extracted_text = extracted_text
                attachment.extraction_metadata = metadata
                await db.flush()

            # Format file content
            if extracted_text:
                file_marker = (
                    f"[file_{idx}: {attachment.original_filename}]\n"
                    f"{extracted_text}\n"
                    f"[end_file_{idx}]"
                )
            else:
                # Extraction failed fallback
                error_msg = "extraction failed"
                if attachment.extraction_metadata:
                    error_msg = attachment.extraction_metadata.get(
                        "extraction_error", error_msg
                    )
                file_marker = (
                    f"[file_{idx}: {attachment.original_filename} - {error_msg}]"
                )

            file_contents.append(file_marker)

    # Build final content: file contents → user message text → images
    final_text_parts = []

    if file_contents:
        final_text_parts.extend(file_contents)

    if message.content and message.content.strip():
        final_text_parts.append(message.content)

    if final_text_parts:
        content_parts.insert(0, {"type": "text", "text": "\n\n".join(final_text_parts)})

    # If only text, return simple format
    if len(content_parts) == 1 and content_parts[0]["type"] == "text":
        return {"role": message.role.value, "content": content_parts[0]["text"]}

    return {"role": message.role.value, "content": content_parts}


async def _extract_memories_background(
    user_id: UUID,
    space_id: UUID | None,
    space_name: str,
    conversation: list[dict],
    conversation_id: UUID | None = None,
) -> None:
    """
    后台异步提取记忆（不阻塞主响应流）。

    Args:
        user_id: 用户 ID
        space_id: 学习空间 ID（可选）
        space_name: 学习空间名称
        conversation: 对话历史列表
        conversation_id: 对话 ID（可选，用于关联活动记录）
    """
    try:
        extractor = MemoryExtractor()
        result = await extractor.extract_and_save(
            user_id=user_id,
            space_id=space_id,
            space_name=space_name,
            conversation=conversation,
            conversation_id=conversation_id,
        )
        if result.long_term_count > 0 or result.space_count > 0:
            logger.info(
                f"Extracted memories for user {user_id}: "
                f"long_term={result.long_term_count}, space={result.space_count}"
            )
    except Exception as e:
        # 记忆提取失败不影响主流程，静默记录错误
        logger.error(
            f"Memory extraction failed for user {user_id}: {e}",
            exc_info=True,
        )


async def _evaluate_mastery_and_notify(
    user_id: UUID,
    space_id: UUID,
    conversation: list[dict],
    is_collaborative: bool = False,
) -> None:
    """
    后台评估掌握分并推送通知（每个节点一条通知）。

    Args:
        user_id: 用户 ID
        space_id: 学习空间 ID
        conversation: 对话历史列表
        is_collaborative: 是否为协作学习空间
    """
    try:
        from graph.mastery_evaluator import MasteryEvaluator
        from notifications.queue import push_notification

        evaluator = MasteryEvaluator(space_id=space_id, user_id=user_id, is_collaborative=is_collaborative)
        result = await evaluator.evaluate_and_update(conversation)

        for update in result.updates:
            if update.change == 0:
                continue
            await push_notification(user_id, {
                "type": "mastery_update",
                "data": {
                    "node_name": update.node_name,
                    "change": update.change,
                    "new_mastery": update.new_mastery,
                },
            })

        if result.success_count > 0:
            logger.info(
                "Mastery evaluation for user %s: %d updates pushed",
                user_id,
                result.success_count,
            )
    except Exception as e:
        logger.error(
            "Mastery evaluation failed for user %s: %s",
            user_id,
            e,
            exc_info=True,
        )


async def _evaluate_mastery_then_expand_path(
    user_id: UUID,
    space_id: UUID,
    conversation: list[dict],
    is_collaborative: bool = False,
) -> None:
    """
    后台链式任务：先评估掌握分，再检查是否需要扩展学习路径。

    Args:
        user_id: 用户 ID
        space_id: 学习空间 ID
        conversation: 对话历史列表
        is_collaborative: 是否为协作学习空间
    """
    # Step 1: 掌握分评估（原有逻辑）
    await _evaluate_mastery_and_notify(user_id, space_id, conversation, is_collaborative=is_collaborative)

    # Step 2: 学习路径扩展检查
    try:
        settings = get_settings()
        if not settings.learning_path_auto_expand_enabled:
            return

        from graph.path_expander import LearningPathExpander
        from notifications.queue import push_notification

        expander = LearningPathExpander(space_id=space_id, user_id=user_id, is_collaborative=is_collaborative)
        result = await expander.check_and_expand()

        if result.expanded:
            await push_notification(user_id, {
                "type": "learning_path_expanded",
                "data": {
                    "space_id": str(space_id),
                    "new_nodes": result.new_path_nodes,
                    "junction_node": result.trigger_info["last_node"] if result.trigger_info else None,
                    "message": f"学习路径已自动扩展，新增 {len(result.new_path_nodes)} 个节点",
                },
            })
    except Exception as e:
        logger.error(
            "Path expansion failed for user %s space %s: %s",
            user_id,
            space_id,
            e,
            exc_info=True,
        )


class ConversationNotFoundError(Exception):
    """Raised when conversation is not found"""

    pass


class ConversationAccessDeniedError(Exception):
    """Raised when user doesn't have access to conversation"""

    pass


class SpaceRequiredError(Exception):
    """Raised when conversation requires a learning space but none is bound"""

    pass


class SpaceNotFoundError(Exception):
    """Raised when learning space is not found"""

    pass


class SpaceAccessDeniedError(Exception):
    """Raised when user doesn't have access to learning space"""

    pass


class ChatService:
    """Service for chat/conversation operations"""

    _active_stream_tasks: dict[str, ActiveStreamTask] = {}

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @classmethod
    def _register_active_stream_task(
        cls,
        conversation_id: UUID,
        task: asyncio.Task,
    ) -> None:
        """Track an active generation task for explicit user stop requests."""
        key = str(conversation_id)
        existing = cls._active_stream_tasks.get(key)
        if existing and existing.task is not task and not existing.task.done():
            logger.warning(
                "Replacing active stream task for conversation %s", conversation_id
            )
            existing.task.cancel()

        cls._active_stream_tasks[key] = ActiveStreamTask(task=task)

        def _cleanup(done_task: asyncio.Task, conv_key: str = key) -> None:
            active = cls._active_stream_tasks.get(conv_key)
            if active and active.task is done_task:
                cls._active_stream_tasks.pop(conv_key, None)

        task.add_done_callback(_cleanup)

    @classmethod
    async def stop_stream(
        cls,
        conversation_id: UUID,
    ) -> dict[str, Any]:
        """Stop an active streaming response for a conversation."""
        key = str(conversation_id)
        state = await get_streaming_state(key)
        active = cls._active_stream_tasks.get(key)
        has_running_task = bool(active and not active.task.done())
        has_active_stream = has_running_task or bool(
            state and not state.is_complete and not state.is_stopped
        )

        if not has_active_stream:
            return {
                "stopped": False,
                "is_streaming": False,
                "is_stopped": bool(state and state.is_stopped),
                "partial_content": (state.content or None) if state else None,
                "partial_thinking": (state.thinking or None) if state else None,
                "tool_calls": (state.tool_calls or []) if state else [],
                "updated_at": state.updated_at if state else None,
            }

        stopped_state = await mark_streaming_stopped(key, reason="user_stopped")
        if has_running_task:
            active.task.cancel()

        return {
            "stopped": True,
            "is_streaming": False,
            "is_stopped": True,
            "partial_content": stopped_state.content or None,
            "partial_thinking": stopped_state.thinking or None,
            "tool_calls": stopped_state.tool_calls or [],
            "updated_at": stopped_state.updated_at,
        }

    async def get_conversation_detail(
        self,
        user_id: UUID,
        conversation_id: UUID,
    ) -> ConversationDetailResponse:
        """
        Get conversation with its messages.

        Args:
            user_id: Current user ID
            conversation_id: Conversation ID

        Returns:
            ConversationDetailResponse with conversation and messages

        Raises:
            ConversationNotFoundError: If conversation not found
            ConversationAccessDeniedError: If user doesn't own the conversation
        """
        conversation = await self._get_conversation_with_check(user_id, conversation_id)

        # Get messages with attachments
        result = await self.db.execute(
            select(Message)
            .options(selectinload(Message.attachments))
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        messages = result.scalars().all()

        return ConversationDetailResponse(
            conversation=ConversationResponse.model_validate(conversation),
            messages=[MessageResponse.model_validate(m) for m in messages],
        )

    @staticmethod
    async def send_message(
        user_id: UUID,
        conversation_id: UUID,
        content: str,
        attachment_ids: list[UUID] | None = None,
        model_id: str | None = None,
        validated_space_id: UUID | None = None,
        panel_screenshot: str | None = None,
        thinking: bool | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Send a message in a conversation and get SSE response stream.

        Static method - does NOT use instance DB session. Manages its own
        short-lived sessions internally via get_scoped_session().

        Three-phase design to minimize DB connection hold time:
        1. Prepare: short-lived session for validation, save user msg, load history
        2. Stream: LLM streaming without holding any DB connection
        3. Save: short-lived session to persist AI response

        Args:
            user_id: Current user ID
            conversation_id: Conversation ID
            content: Message content
            attachment_ids: Optional attachment IDs
            model_id: Optional model ID for per-message model selection
            validated_space_id: Space ID already validated by router (skip re-validation)

        Yields:
            SSE events for streaming response

        Raises:
            ConversationNotFoundError: If conversation not found
            ConversationAccessDeniedError: If user doesn't own the conversation
            SpaceRequiredError: If conversation has no bound learning space
        """
        t_phase1_start = time.monotonic()

        # === Phase 1: Prepare (short-lived DB session) ===
        async with get_scoped_session() as db:
            # 1. Validate conversation ownership (skip if already validated by router)
            if validated_space_id:
                space_id = validated_space_id
            else:
                t0 = time.monotonic()
                result = await db.execute(
                    select(Conversation).where(
                        Conversation.id == conversation_id,
                        Conversation.kind == ConversationKind.LEARNING,
                    )
                )
                conversation = result.scalar_one_or_none()

                if not conversation:
                    raise ConversationNotFoundError(f"对话 {conversation_id} 不存在")
                if conversation.user_id != user_id:
                    raise ConversationAccessDeniedError(f"无权访问对话 {conversation_id}")

                if not conversation.space_id:
                    raise SpaceRequiredError("对话必须绑定到学习空间才能使用知识图谱功能")

                space_id = conversation.space_id
                logger.info(f"[Perf] Validate conversation: {(time.monotonic()-t0)*1000:.0f}ms")

            # 3. Save user message
            t0 = time.monotonic()
            user_message = Message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=content,
            )
            db.add(user_message)
            await db.flush()  # Get ID without committing

            # 3.5. Attach attachments to message if any
            if attachment_ids:
                from attachments.service import AttachmentService

                attachment_service = AttachmentService(db)
                await attachment_service.attach_to_message(
                    user_id=user_id,
                    message_id=user_message.id,
                    attachment_ids=attachment_ids,
                    commit=False,  # Don't commit yet
                )

            # Commit both user message and attachments in single transaction
            await db.commit()

            # Record study activity (fire-and-forget)
            from assessment.recorder import schedule_study_activity_recording
            schedule_study_activity_recording(user_id)

            # Refresh and load attachments relationship
            await db.refresh(user_message, ["attachments"])
            logger.info(f"[Perf] Save user message: {(time.monotonic()-t0)*1000:.0f}ms")

            # 4. Load recent history messages (with attachments preloaded)
            t0 = time.monotonic()
            history_result = await db.execute(
                select(Message)
                .options(selectinload(Message.attachments))
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(MAX_HISTORY_MESSAGES + 1)
            )
            history_messages = list(reversed(history_result.scalars().all()))
            logger.info(f"[Perf] Load history ({len(history_messages)} msgs): {(time.monotonic()-t0)*1000:.0f}ms")

            # Build LLM history with attachments (async)
            t0 = time.monotonic()
            llm_history = []
            for m in history_messages[:-1]:
                msg_dict = await _build_llm_message_with_attachments_async(m, db)
                llm_history.append(msg_dict)

            # Build current message with attachments (async, includes file content extraction)
            current_message_dict = await _build_llm_message_with_attachments_async(
                user_message, db
            )
            current_message_image_urls = _extract_image_urls_from_llm_message(
                current_message_dict
            )

            # Inject panel screenshot into current message (transient, not saved to DB)
            if panel_screenshot:
                if isinstance(current_message_dict["content"], str):
                    current_message_dict["content"] = [
                        {"type": "text", "text": current_message_dict["content"]},
                    ]
                current_message_dict["content"].insert(0, {
                    "type": "image_url",
                    "image_url": {"url": panel_screenshot},
                })

            logger.info(f"[Perf] Build LLM history: {(time.monotonic()-t0)*1000:.0f}ms")

            # 5. Get space info
            t0 = time.monotonic()
            space_result = await db.execute(
                select(Space).where(Space.id == space_id)
            )
            space = space_result.scalar_one_or_none()

            if not space:
                raise SpaceRequiredError("绑定的学习空间不存在")

            space_name = space.name
            space_tool_mode = getattr(space, "tool_mode", "auto") or "auto"
            space_enabled_tools = getattr(space, "enabled_tools", None)
            space_is_collaborative = getattr(space, "is_collaborative", False) or False
            space_can_edit_graph = await _resolve_space_graph_edit_permission(
                db, space, user_id
            )
            logger.info(f"[Perf] Load space info: {(time.monotonic()-t0)*1000:.0f}ms")

            # 6. 对话连续性：检测新对话并加载上一次对话上下文
            # 新对话定义：当前对话只有刚发送的这一条消息
            is_new_conversation = len(history_messages) == 1
            previous_conversation_context = None

            t0 = time.monotonic()
            settings = get_settings()
            if is_new_conversation and settings.conversation_continuity_enabled:
                from chat.previous_conversation import get_previous_conversation_context

                previous_conversation_context = await get_previous_conversation_context(
                    db=db,
                    user_id=user_id,
                    space_id=space_id,
                    current_conversation_id=conversation_id,
                    max_rounds=settings.conversation_continuity_max_rounds,
                    max_content_length=settings.conversation_continuity_max_content_length,
                )
                if previous_conversation_context:
                    logger.debug(
                        f"Loaded previous conversation context for new conversation {conversation_id}"
                    )
            logger.info(f"[Perf] Previous context: {(time.monotonic()-t0)*1000:.0f}ms")
        # === DB session released here ===

        logger.info(f"[Perf] Phase 1 total: {(time.monotonic()-t_phase1_start)*1000:.0f}ms")

        # === Start title generation concurrently (for new conversations) ===
        title_task = None
        settings = get_settings()
        if is_new_conversation and settings.title_generation_enabled:
            title_task = asyncio.create_task(
                generate_title(
                    content,
                    user_id=user_id,
                    conversation_id=conversation_id,
                )
            )

        # === Load user search settings ===
        t0 = time.monotonic()
        from search_settings.service import SearchSettingsService
        enabled_channels = await SearchSettingsService.get_enabled_channels(user_id)
        logger.info(f"[Perf] Search settings: {(time.monotonic()-t0)*1000:.0f}ms")

        # === Phase 2: Stream via Queue + Background Task ===
        # Orchestrator runs in an independent background task so that client
        # disconnect does NOT cancel LLM generation.  Events flow through an
        # asyncio.Queue; the SSE generator reads from it.  When the client
        # disconnects the generator stops, but the background task keeps running
        # and always executes Phase 3 (save).
        # Resolve model_id to DashScope model string
        llm_model = get_model_id(model_id)
        max_output_tokens = get_max_output_tokens(model_id)
        logger.info(f"[ModelSelection] study model_id={model_id!r} -> llm_model={llm_model!r}, max_output_tokens={max_output_tokens}")

        # Resolve thinking: only honor if model supports it
        from chat.models_config import get_supports_thinking
        enable_thinking = thinking if get_supports_thinking(model_id) else None

        orchestrator = LLMOrchestrator(
            user_id=user_id,
            conversation_id=conversation_id,
            space_id=space_id,
            space_name=space_name,
            previous_conversation_context=previous_conversation_context,
            llm_model=llm_model,
            search_channels=enabled_channels,
            tool_mode=space_tool_mode,
            enabled_tools=space_enabled_tools,
            has_panel_screenshot=bool(panel_screenshot),
            is_collaborative=space_is_collaborative,
            can_edit_graph=space_can_edit_graph,
            max_output_tokens=max_output_tokens,
            enable_thinking=enable_thinking,
        )

        queue: asyncio.Queue = asyncio.Queue()

        async def _run_to_completion() -> None:
            """Background task: runs orchestrator to completion, then saves result."""
            full_response = ""
            llm_context = None
            citations = None
            response_status = MessageResponseStatus.COMPLETED
            finalized = False

            async def _finalize_after_generation() -> None:
                nonlocal finalized
                if finalized:
                    return
                finalized = True

                if full_response:
                    stream_state = await get_streaming_state(str(conversation_id))
                    try:
                        await _persist_assistant_message(
                            conversation_id=conversation_id,
                            content=full_response,
                            llm_context=llm_context,
                            citations=citations,
                            response_status=response_status,
                            tool_calls=stream_state.tool_calls if stream_state and stream_state.tool_calls else None,
                        )
                    except Exception:
                        logger.critical(
                            f"Failed to save assistant response for conversation {conversation_id}, "
                            f"response length: {len(full_response)}.",
                            exc_info=True,
                        )

                    if response_status == MessageResponseStatus.COMPLETED:
                        _settings = get_settings()
                        if _settings.memory_auto_extract_enabled:
                            conversation_for_extraction = llm_history + [
                                {"role": "user", "content": content},
                                {"role": "assistant", "content": full_response},
                            ]
                            asyncio.create_task(
                                _extract_memories_background(
                                    user_id=user_id,
                                    space_id=space_id,
                                    space_name=space_name,
                                    conversation=conversation_for_extraction,
                                    conversation_id=conversation_id,
                                )
                            )

                        if _settings.mastery_evaluation_enabled and space_id:
                            conversation_for_evaluation = llm_history + [
                                {"role": "user", "content": content},
                                {"role": "assistant", "content": full_response},
                            ]
                            asyncio.create_task(
                                _evaluate_mastery_then_expand_path(
                                    user_id=user_id,
                                    space_id=space_id,
                                    conversation=conversation_for_evaluation,
                                    is_collaborative=space_is_collaborative,
                                )
                            )

                if title_task is None:
                    return

                if response_status == MessageResponseStatus.STOPPED:
                    if not title_task.done():
                        title_task.cancel()
                        try:
                            await title_task
                        except (asyncio.CancelledError, Exception):
                            pass
                    return

                _title_timeout = get_settings().title_generation_timeout
                try:
                    title = await asyncio.wait_for(title_task, timeout=_title_timeout)
                except asyncio.TimeoutError:
                    logger.warning(f"[TitleGen] Timed out after {_title_timeout}s for {conversation_id}")
                    title = fallback_title(content)
                    if not title_task.done():
                        title_task.cancel()
                        try:
                            await title_task
                        except (asyncio.CancelledError, Exception):
                            pass
                except Exception as e:
                    logger.warning(f"[TitleGen] Failed for {conversation_id}: {type(e).__name__}: {e}")
                    title = fallback_title(content)

                try:
                    async with get_scoped_session() as save_db:
                        result = await save_db.execute(
                            select(Conversation).where(
                                Conversation.id == conversation_id,
                                Conversation.kind == ConversationKind.LEARNING,
                            )
                        )
                        conv = result.scalar_one_or_none()
                        if conv:
                            conv.title = title[:200]
                            await save_db.commit()
                    await queue.put({"event": "title", "data": {"title": title}})
                except Exception:
                    logger.error(
                        f"Failed to update title for conversation {conversation_id}",
                        exc_info=True,
                    )

            try:
                try:
                    async for event in orchestrator.process_message(
                        current_message_dict,
                        llm_history,
                        current_message_image_urls=current_message_image_urls,
                    ):
                        if event["event"] == "text_delta":
                            full_response += event["data"].get("content", "")
                        elif event["event"] == "done":
                            full_response = event["data"].get("content", full_response)
                            llm_context = event["data"].get("llm_context")
                            citations = event["data"].get("citations")
                            # Strip llm_context from SSE payload, keep citations for frontend
                            event = {
                                "event": "done",
                                "data": {
                                    "content": full_response,
                                    "citations": citations,
                                    "response_status": MessageResponseStatus.COMPLETED.value,
                                },
                            }
                        await queue.put(event)
                except asyncio.CancelledError:
                    response_status = MessageResponseStatus.STOPPED
                    logger.info(
                        "Streaming response stopped for conversation %s with %d chars generated",
                        conversation_id,
                        len(full_response),
                    )
                    raise
                except Exception as e:
                    logger.error(f"Orchestrator error: {e}", exc_info=True)
                    await queue.put({"event": "error", "data": {"message": str(e)}})

                await _finalize_after_generation()

                logger.info(
                    f"Processed message in conversation {conversation_id}, "
                    f"response length: {len(full_response)}"
                )
            except asyncio.CancelledError:
                response_status = MessageResponseStatus.STOPPED
                await _finalize_after_generation()
                logger.info(
                    "Stopped background generation for conversation %s",
                    conversation_id,
                )
            finally:
                # Sentinel: signal consumer to stop (always sent)
                await queue.put(None)

        # Start background task (fire-and-forget — survives client disconnect)
        task = asyncio.create_task(_run_to_completion())
        task.add_done_callback(_log_task_exception)
        ChatService._register_active_stream_task(conversation_id, task)

        # Yield events from queue to SSE client
        while True:
            event = await queue.get()
            if event is None:
                break
            yield event

    async def validate_conversation_access(
        self,
        user_id: UUID,
        conversation_id: UUID,
        require_space: bool = False,
    ) -> Conversation:
        """
        Validate user has access to conversation.

        Args:
            user_id: Current user ID
            conversation_id: Conversation ID
            require_space: If True, also validate space is bound

        Returns:
            Conversation object

        Raises:
            ConversationNotFoundError: If conversation not found
            ConversationAccessDeniedError: If user doesn't own the conversation
            SpaceRequiredError: If require_space=True and no space bound
        """
        conversation = await self._get_conversation_with_check(user_id, conversation_id)

        if require_space and not conversation.space_id:
            raise SpaceRequiredError("对话必须绑定到学习空间才能使用知识图谱功能")

        return conversation

    async def create_conversation(
        self,
        user_id: UUID,
        space_id: UUID,
        title: str,
    ) -> ConversationResponse:
        """
        Create a new conversation for a learning space.

        Args:
            user_id: Current user ID
            space_id: Learning space ID
            title: Conversation title

        Returns:
            ConversationResponse

        Raises:
            SpaceNotFoundError: If space not found
            SpaceAccessDeniedError: If user doesn't own the space
        """
        # Validate space ownership
        space = await self._get_space_with_check(user_id, space_id)

        conversation = Conversation(
            user_id=user_id,
            space_id=space_id,
            title=title[:200],  # Ensure max length
            kind=ConversationKind.LEARNING,
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)

        logger.info(f"Created conversation {conversation.id} in space {space_id}")
        return ConversationResponse.model_validate(conversation)

    async def list_conversations(
        self,
        user_id: UUID,
        space_id: UUID,
    ) -> ConversationListResponse:
        """
        List all conversations for a learning space.

        Args:
            user_id: Current user ID
            space_id: Learning space ID

        Returns:
            ConversationListResponse with conversations list and total count

        Raises:
            SpaceNotFoundError: If space not found
            SpaceAccessDeniedError: If user doesn't own the space
        """
        # Validate space ownership
        await self._get_space_with_check(user_id, space_id)

        # Get conversations
        result = await self.db.execute(
            select(Conversation)
            .where(
                Conversation.space_id == space_id,
                Conversation.user_id == user_id,
                Conversation.kind == ConversationKind.LEARNING,
            )
            .order_by(Conversation.updated_at.desc())
        )
        conversations = result.scalars().all()

        return ConversationListResponse(
            conversations=[ConversationResponse.model_validate(c) for c in conversations],
            total=len(conversations),
        )

    async def search_conversations(
        self,
        user_id: UUID,
        space_id: UUID,
        q: str,
        scope: str = "all",
        page: int = 1,
        page_size: int = 20,
    ) -> ConversationSearchResponse:
        """
        Search conversations within a learning space.

        Args:
            user_id: Current user ID
            space_id: Learning space ID (results are scoped to this space)
            q: Search query
            scope: "title" | "content" | "all"
            page: Page number (1-based)
            page_size: Results per page (max 50)

        Returns:
            ConversationSearchResponse

        Raises:
            SpaceNotFoundError: If space not found
            SpaceAccessDeniedError: If user doesn't own the space
        """
        await self._get_space_with_check(user_id, space_id)

        page_size = min(page_size, 50)
        pattern = f"%{q}%"

        # Build base query scoped to space + user
        base_query = (
            select(Conversation)
            .distinct()
            .where(
                Conversation.space_id == space_id,
                Conversation.user_id == user_id,
                Conversation.kind == ConversationKind.LEARNING,
            )
        )

        if scope == "title":
            base_query = base_query.where(Conversation.title.ilike(pattern))
        elif scope == "content":
            base_query = (
                base_query
                .outerjoin(Message, Message.conversation_id == Conversation.id)
                .where(Message.content.ilike(pattern))
            )
        else:  # "all"
            base_query = (
                base_query
                .outerjoin(Message, Message.conversation_id == Conversation.id)
                .where(
                    or_(
                        Conversation.title.ilike(pattern),
                        Message.content.ilike(pattern),
                    )
                )
            )

        # Count total matching conversations
        count_result = await self.db.scalar(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result or 0

        # Fetch paginated conversations
        paginated = base_query.order_by(Conversation.updated_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size)

        conv_result = await self.db.execute(paginated)
        conversations = conv_result.scalars().all()

        # For each conversation, fetch up to 3 matching messages (skip for title-only scope)
        items = []
        for conv in conversations:
            if scope == "title":
                matching_messages = []
            else:
                msg_result = await self.db.execute(
                    select(Message)
                    .where(
                        Message.conversation_id == conv.id,
                        Message.content.ilike(pattern),
                    )
                    .order_by(Message.created_at.asc())
                    .limit(3)
                )
                msgs = msg_result.scalars().all()
                matching_messages = [
                    MessageSnippet(
                        id=m.id,
                        role=m.role.value,
                        snippet=_extract_snippet(m.content, q),
                        created_at=m.created_at,
                    )
                    for m in msgs
                ]

            items.append(
                ConversationSearchItem(
                    id=conv.id,
                    title=conv.title,
                    space_id=conv.space_id,
                    updated_at=conv.updated_at,
                    created_at=conv.created_at,
                    matching_messages=matching_messages,
                )
            )

        return ConversationSearchResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            query=q,
        )

    async def delete_conversation(
        self,
        user_id: UUID,
        conversation_id: UUID,
    ) -> None:
        """
        Delete a conversation.

        Args:
            user_id: Current user ID
            conversation_id: Conversation ID

        Raises:
            ConversationNotFoundError: If conversation not found
            ConversationAccessDeniedError: If user doesn't own the conversation
        """
        conversation = await self._get_conversation_with_check(user_id, conversation_id)

        # Delete conversation (messages will be cascade deleted)
        await self.db.delete(conversation)
        await self.db.commit()

        logger.info(f"Deleted conversation {conversation_id}")

    async def rollback_last_message(
        self,
        user_id: UUID,
        conversation_id: UUID,
    ) -> int:
        """
        Roll back the last user message and all subsequent messages.

        Finds the most recent user message in the conversation and deletes
        it along with any AI replies that followed.

        Args:
            user_id: Current user ID
            conversation_id: Conversation ID

        Returns:
            Number of deleted messages

        Raises:
            ConversationNotFoundError: If conversation not found
            ConversationAccessDeniedError: If user doesn't own the conversation
        """
        await self._get_conversation_with_check(user_id, conversation_id)

        # Find the last user message
        result = await self.db.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.role == MessageRole.USER,
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_user_msg = result.scalar_one_or_none()

        if not last_user_msg:
            return 0

        cutoff_created_at = last_user_msg.created_at
        if cutoff_created_at.tzinfo is not None:
            cutoff_created_at = cutoff_created_at.astimezone(timezone.utc).replace(
                tzinfo=None
            )

        # Delete that message and all messages after it
        result = await self.db.execute(
            delete(Message).where(
                Message.conversation_id == conversation_id,
                Message.created_at >= cutoff_created_at,
            )
        )
        deleted_count = result.rowcount
        await self.db.commit()

        logger.info(
            f"Rolled back conversation {conversation_id}: "
            f"deleted {deleted_count} messages"
        )
        return deleted_count

    async def _get_space_with_check(
        self,
        user_id: UUID,
        space_id: UUID,
    ) -> Space:
        """
        Get space with access validation (owner OR member).

        Raises:
            SpaceNotFoundError: If space not found
            SpaceAccessDeniedError: If user doesn't have access
        """
        from spaces.authorization import verify_space_access as _verify
        from spaces.authorization import (
            SpaceAccessDeniedError as _AccessDenied,
            SpaceNotFoundError as _NotFound,
        )

        try:
            return await _verify(self.db, space_id, user_id)
        except _NotFound:
            raise SpaceNotFoundError(f"学习空间 {space_id} 不存在")
        except _AccessDenied:
            raise SpaceAccessDeniedError(f"无权访问学习空间 {space_id}")

    async def _get_conversation_with_check(
        self,
        user_id: UUID,
        conversation_id: UUID,
    ) -> Conversation:
        """
        Get conversation with ownership validation (internal).

        Raises:
            ConversationNotFoundError: If conversation not found
            ConversationAccessDeniedError: If user doesn't own the conversation
        """
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.kind == ConversationKind.LEARNING,
            )
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise ConversationNotFoundError(f"对话 {conversation_id} 不存在")

        if conversation.user_id != user_id:
            raise ConversationAccessDeniedError(f"无权访问对话 {conversation_id}")

        return conversation

    async def update_conversation(
        self,
        user_id: UUID,
        conversation_id: UUID,
        request: UpdateConversationRequest,
    ) -> ConversationResponse:
        """
        Update conversation properties.

        Args:
            user_id: Current user ID
            conversation_id: Conversation ID
            request: Update request with optional space_id and title

        Returns:
            Updated ConversationResponse

        Raises:
            ConversationNotFoundError: If conversation not found
            ConversationAccessDeniedError: If user doesn't own the conversation
            SpaceNotFoundError: If target space not found
            SpaceAccessDeniedError: If user doesn't own the target space
        """
        conversation = await self._get_conversation_with_check(user_id, conversation_id)

        # If binding to a space, validate space ownership
        if request.space_id is not None:
            await self._get_space_with_check(user_id, request.space_id)
            conversation.space_id = request.space_id

        if request.title is not None:
            conversation.title = request.title[:200]

        await self.db.commit()
        await self.db.refresh(conversation)

        logger.info(f"Updated conversation {conversation_id}")
        return ConversationResponse.model_validate(conversation)
