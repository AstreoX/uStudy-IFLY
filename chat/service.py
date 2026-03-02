"""Chat Service - Conversation and Message Management"""

import asyncio
import base64
import logging
import os
import time
from pathlib import Path
from typing import Any, AsyncGenerator
from uuid import UUID

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from chat.models_config import get_openrouter_model
from chat.orchestrator import LLMOrchestrator, QuickChatOrchestrator
from chat.title_generator import generate_title, fallback_title
from memory.extractor import MemoryExtractor
from chat.schemas import (
    MessageResponse,
    ConversationDetailResponse,
    ConversationResponse,
    ConversationListResponse,
    UpdateConversationRequest,
)
from config import get_settings
from db.database import get_scoped_session
from db.models import Conversation, Message, MessageRole, Space, MessageAttachment, AttachmentType

logger = logging.getLogger(__name__)


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

# Context window limit - how many messages to include in LLM context
# DeepSeek V3 has 128K context window, so we can include more history
MAX_HISTORY_MESSAGES = 50


def _log_task_exception(task: asyncio.Task) -> None:
    """Done callback to log unhandled exceptions in background tasks."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error(f"Background chat task failed: {exc}", exc_info=exc)

# Use base64 encoding for images by default (localhost URLs not accessible to OpenRouter)
USE_BASE64_FOR_IMAGES = os.getenv("USE_BASE64_FOR_IMAGES", "true").lower() == "true"


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
    content_parts = []

    # 1. Add text part (if any)
    if message.content and message.content.strip():
        content_parts.append({"type": "text", "text": message.content})

    # 2. Add image parts
    for attachment in message.attachments:
        if attachment.attachment_type == AttachmentType.IMAGE:
            # Use base64 encoding or URL based on config
            if USE_BASE64_FOR_IMAGES:
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
            if USE_BASE64_FOR_IMAGES:
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
) -> None:
    """
    后台评估掌握分并推送通知（每个节点一条通知）。

    Args:
        user_id: 用户 ID
        space_id: 学习空间 ID
        conversation: 对话历史列表
    """
    try:
        from graph.mastery_evaluator import MasteryEvaluator
        from notifications.queue import push_notification

        evaluator = MasteryEvaluator(space_id=space_id)
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
) -> None:
    """
    后台链式任务：先评估掌握分，再检查是否需要扩展学习路径。

    Args:
        user_id: 用户 ID
        space_id: 学习空间 ID
        conversation: 对话历史列表
    """
    # Step 1: 掌握分评估（原有逻辑）
    await _evaluate_mastery_and_notify(user_id, space_id, conversation)

    # Step 2: 学习路径扩展检查
    try:
        settings = get_settings()
        if not settings.learning_path_auto_expand_enabled:
            return

        from graph.path_expander import LearningPathExpander
        from notifications.queue import push_notification

        expander = LearningPathExpander(space_id=space_id, user_id=user_id)
        result = await expander.check_and_expand()

        if result.expanded:
            await push_notification(user_id, {
                "type": "learning_path_expanded",
                "data": {
                    "space_id": str(space_id),
                    "new_nodes": result.new_path_nodes,
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

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

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
                    select(Conversation).where(Conversation.id == conversation_id)
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
            title_task = asyncio.create_task(generate_title(content))

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
        # Resolve model_id to OpenRouter model string
        openrouter_model = get_openrouter_model(model_id)
        logger.info(f"[ModelSelection] study model_id={model_id!r} -> openrouter_model={openrouter_model!r}")

        orchestrator = LLMOrchestrator(
            user_id=user_id,
            conversation_id=conversation_id,
            space_id=space_id,
            space_name=space_name,
            previous_conversation_context=previous_conversation_context,
            openrouter_model=openrouter_model,
            search_channels=enabled_channels,
        )

        queue: asyncio.Queue = asyncio.Queue()

        async def _run_to_completion() -> None:
            """Background task: runs orchestrator to completion, then saves result."""
            full_response = ""
            llm_context = None
            try:
                try:
                    async for event in orchestrator.process_message(
                        current_message_dict, llm_history
                    ):
                        if event["event"] == "text_delta":
                            full_response += event["data"].get("content", "")
                        elif event["event"] == "done":
                            full_response = event["data"].get("content", full_response)
                            llm_context = event["data"].get("llm_context")
                            # Strip llm_context from SSE payload
                            event = {"event": "done", "data": {"content": full_response}}
                        await queue.put(event)
                except Exception as e:
                    logger.error(f"Orchestrator error: {e}", exc_info=True)
                    await queue.put({"event": "error", "data": {"message": str(e)}})

                # === Phase 3: Save (ALWAYS runs, even after client disconnect) ===
                if full_response:
                    try:
                        async with get_scoped_session() as save_db:
                            assistant_message = Message(
                                conversation_id=conversation_id,
                                role=MessageRole.ASSISTANT,
                                content=full_response,
                                llm_context=llm_context,
                                tool_calls=_extract_tool_calls_from_context(llm_context),
                            )
                            save_db.add(assistant_message)
                            await save_db.commit()
                    except Exception:
                        logger.critical(
                            f"Failed to save assistant response for conversation {conversation_id}, "
                            f"response length: {len(full_response)}.",
                            exc_info=True,
                        )

                    # Phase 3.5: 异步触发记忆提取
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

                    # Phase 3.6: 异步掌握分评估 + 学习路径扩展
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
                            )
                        )

                # Phase 3.7: Auto-generate title for new conversations
                if title_task is not None:
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
                                select(Conversation).where(Conversation.id == conversation_id)
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

                logger.info(
                    f"Processed message in conversation {conversation_id}, "
                    f"response length: {len(full_response)}"
                )
            finally:
                # Sentinel: signal consumer to stop (always sent)
                await queue.put(None)

        # Start background task (fire-and-forget — survives client disconnect)
        task = asyncio.create_task(_run_to_completion())
        task.add_done_callback(_log_task_exception)

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
            .where(Conversation.space_id == space_id, Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        conversations = result.scalars().all()

        return ConversationListResponse(
            conversations=[ConversationResponse.model_validate(c) for c in conversations],
            total=len(conversations),
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

    async def _get_space_with_check(
        self,
        user_id: UUID,
        space_id: UUID,
    ) -> Space:
        """
        Get space with ownership validation (internal).

        Raises:
            SpaceNotFoundError: If space not found
            SpaceAccessDeniedError: If user doesn't own the space
        """
        result = await self.db.execute(
            select(Space).where(Space.id == space_id)
        )
        space = result.scalar_one_or_none()

        if not space:
            raise SpaceNotFoundError(f"学习空间 {space_id} 不存在")

        if space.user_id != user_id:
            raise SpaceAccessDeniedError(f"无权访问学习空间 {space_id}")

        return space

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
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise ConversationNotFoundError(f"对话 {conversation_id} 不存在")

        if conversation.user_id != user_id:
            raise ConversationAccessDeniedError(f"无权访问对话 {conversation_id}")

        return conversation

    async def create_quick_chat_conversation(
        self,
        user_id: UUID,
        title: str,
    ) -> ConversationResponse:
        """
        Create a conversation without space binding (quick chat mode).

        Args:
            user_id: Current user ID
            title: Conversation title

        Returns:
            ConversationResponse
        """
        conversation = Conversation(
            user_id=user_id,
            space_id=None,  # No space binding for quick chat
            title=title[:200],
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)

        logger.info(f"Created quick chat conversation {conversation.id}")
        return ConversationResponse.model_validate(conversation)

    async def list_quick_chat_conversations(
        self,
        user_id: UUID,
    ) -> ConversationListResponse:
        """
        List conversations without space binding (quick chat).

        Args:
            user_id: Current user ID

        Returns:
            ConversationListResponse with conversations list
        """
        result = await self.db.execute(
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.space_id.is_(None)
            )
            .order_by(Conversation.updated_at.desc())
        )
        conversations = result.scalars().all()

        return ConversationListResponse(
            conversations=[ConversationResponse.model_validate(c) for c in conversations],
            total=len(conversations),
        )

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

    @staticmethod
    async def send_quick_chat_message(
        user_id: UUID,
        conversation_id: UUID,
        content: str,
        attachment_ids: list[UUID] | None = None,
        model_id: str | None = None,
        validated: bool = False,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Send message in quick chat mode (no space required).

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
            validated: If True, skip conversation ownership check (already done by router)

        Yields:
            SSE events for streaming response

        Raises:
            ConversationNotFoundError: If conversation not found
            ConversationAccessDeniedError: If user doesn't own the conversation
        """
        t_phase1_start = time.monotonic()

        # === Phase 1: Prepare (short-lived DB session) ===
        async with get_scoped_session() as db:
            # 1. Validate conversation (skip if already validated by router)
            if not validated:
                t0 = time.monotonic()
                result = await db.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conversation = result.scalar_one_or_none()

                if not conversation:
                    raise ConversationNotFoundError(f"对话 {conversation_id} 不存在")
                if conversation.user_id != user_id:
                    raise ConversationAccessDeniedError(f"无权访问对话 {conversation_id}")
                logger.info(f"[Perf][QC] Validate conversation: {(time.monotonic()-t0)*1000:.0f}ms")

            # 2. Save user message
            t0 = time.monotonic()
            user_message = Message(
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=content,
            )
            db.add(user_message)
            await db.flush()  # Get ID without committing

            # 2.5. Attach attachments to message if any
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
            logger.info(f"[Perf][QC] Save user message: {(time.monotonic()-t0)*1000:.0f}ms")

            # 3. Load recent history messages (with attachments preloaded)
            t0 = time.monotonic()
            history_result = await db.execute(
                select(Message)
                .options(selectinload(Message.attachments))
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(MAX_HISTORY_MESSAGES + 1)
            )
            history_messages = list(reversed(history_result.scalars().all()))
            logger.info(f"[Perf][QC] Load history ({len(history_messages)} msgs): {(time.monotonic()-t0)*1000:.0f}ms")

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
            logger.info(f"[Perf][QC] Build LLM history: {(time.monotonic()-t0)*1000:.0f}ms")

            # 4. 对话连续性：检测新对话并加载上一个对话上下文
            # 新对话定义：当前对话只有刚发送的这一条消息
            is_new_conversation = len(history_messages) == 1
            previous_conversation_context = None

            t0 = time.monotonic()
            settings = get_settings()
            if is_new_conversation and settings.conversation_continuity_enabled:
                from chat.previous_conversation import (
                    get_previous_conversation_context_global,
                )

                previous_conversation_context = (
                    await get_previous_conversation_context_global(
                        db=db,
                        user_id=user_id,
                        current_conversation_id=conversation_id,
                        max_rounds=settings.conversation_continuity_max_rounds,
                        max_content_length=settings.conversation_continuity_max_content_length,
                    )
                )
                if previous_conversation_context:
                    logger.debug(
                        f"Loaded global previous conversation context for quick chat {conversation_id}"
                    )
            logger.info(f"[Perf][QC] Previous context: {(time.monotonic()-t0)*1000:.0f}ms")
        # === DB session released here ===

        logger.info(f"[Perf][QC] Phase 1 total: {(time.monotonic()-t_phase1_start)*1000:.0f}ms")

        # === Start title generation concurrently (for new conversations) ===
        title_task = None
        settings = get_settings()
        if is_new_conversation and settings.title_generation_enabled:
            title_task = asyncio.create_task(generate_title(content))

        # === Load user search settings ===
        t0 = time.monotonic()
        from search_settings.service import SearchSettingsService
        enabled_channels = await SearchSettingsService.get_enabled_channels(user_id)
        logger.info(f"[Perf][QC] Search settings: {(time.monotonic()-t0)*1000:.0f}ms")

        # === Phase 2: Stream via Queue + Background Task ===
        # Resolve model_id to OpenRouter model string
        openrouter_model = get_openrouter_model(model_id)
        logger.info(f"[ModelSelection] quick_chat model_id={model_id!r} -> openrouter_model={openrouter_model!r}")

        orchestrator = QuickChatOrchestrator(
            user_id=user_id,
            conversation_id=conversation_id,
            previous_conversation_context=previous_conversation_context,
            openrouter_model=openrouter_model,
            search_channels=enabled_channels,
        )

        queue: asyncio.Queue = asyncio.Queue()

        async def _run_to_completion() -> None:
            """Background task: runs orchestrator to completion, then saves result."""
            full_response = ""
            llm_context = None
            try:
                try:
                    async for event in orchestrator.process_message(
                        current_message_dict, llm_history
                    ):
                        if event["event"] == "text_delta":
                            full_response += event["data"].get("content", "")
                        elif event["event"] == "done":
                            full_response = event["data"].get("content", full_response)
                            llm_context = event["data"].get("llm_context")
                            event = {"event": "done", "data": {"content": full_response}}
                        await queue.put(event)
                except Exception as e:
                    logger.error(f"Orchestrator error: {e}", exc_info=True)
                    await queue.put({"event": "error", "data": {"message": str(e)}})

                # === Phase 3: Save (ALWAYS runs) ===
                if full_response:
                    try:
                        async with get_scoped_session() as save_db:
                            assistant_message = Message(
                                conversation_id=conversation_id,
                                role=MessageRole.ASSISTANT,
                                content=full_response,
                                llm_context=llm_context,
                                tool_calls=_extract_tool_calls_from_context(llm_context),
                            )
                            save_db.add(assistant_message)
                            await save_db.commit()
                    except Exception:
                        logger.critical(
                            f"Failed to save assistant response for quick chat {conversation_id}, "
                            f"response length: {len(full_response)}.",
                            exc_info=True,
                        )

                    # Phase 3.5: 异步触发记忆提取
                    _settings = get_settings()
                    if _settings.memory_auto_extract_enabled:
                        conversation_for_extraction = llm_history + [
                            {"role": "user", "content": content},
                            {"role": "assistant", "content": full_response},
                        ]
                        asyncio.create_task(
                            _extract_memories_background(
                                user_id=user_id,
                                space_id=None,
                                space_name="快速对话",
                                conversation=conversation_for_extraction,
                                conversation_id=conversation_id,
                            )
                        )

                # Phase 3.7: Auto-generate title for new conversations
                if title_task is not None:
                    _title_timeout = get_settings().title_generation_timeout
                    try:
                        title = await asyncio.wait_for(title_task, timeout=_title_timeout)
                    except asyncio.TimeoutError:
                        logger.warning(f"[TitleGen] Timed out after {_title_timeout}s for quick chat {conversation_id}")
                        title = fallback_title(content)
                        if not title_task.done():
                            title_task.cancel()
                            try:
                                await title_task
                            except (asyncio.CancelledError, Exception):
                                pass
                    except Exception as e:
                        logger.warning(f"[TitleGen] Failed for quick chat {conversation_id}: {type(e).__name__}: {e}")
                        title = fallback_title(content)

                    try:
                        async with get_scoped_session() as save_db:
                            result = await save_db.execute(
                                select(Conversation).where(Conversation.id == conversation_id)
                            )
                            conv = result.scalar_one_or_none()
                            if conv:
                                conv.title = title[:200]
                                await save_db.commit()
                        await queue.put({"event": "title", "data": {"title": title}})
                    except Exception:
                        logger.error(
                            f"Failed to update title for quick chat {conversation_id}",
                            exc_info=True,
                        )

                logger.info(
                    f"Processed quick chat message in conversation {conversation_id}, "
                    f"response length: {len(full_response)}"
                )
            finally:
                # Sentinel: signal consumer to stop (always sent)
                await queue.put(None)

        # Start background task
        task = asyncio.create_task(_run_to_completion())
        task.add_done_callback(_log_task_exception)

        # Yield events from queue to SSE client
        while True:
            event = await queue.get()
            if event is None:
                break
            yield event
