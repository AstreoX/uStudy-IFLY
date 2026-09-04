"""LLM Orchestrator - Multi-turn tool calling loop with SSE"""

import asyncio
import copy
import json
import logging
import time
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select

from agents.llm.client import LLMClient, ToolCall
from agents.llm.stream_driver import stream_tool_completion
from usage.models import UsageType
from usage.metering import UsageContext
from chat.context_collector import IterationData, LLMContextCollector
from chat.prompt_builder import PromptBuilder
from chat.context_futures import ContextFutures
from chat.agent_todo_service import get_agent_todo_prompt_state
from chat.rag_auto_inject import filter_auto_rag_results, should_skip_auto_rag
from chat.tools.catalog import (
    GET_TOOL_DETAILS_TOOL,
    execute_get_tool_details,
    format_catalog_for_prompt,
    get_tools_for_manual_mode,
)
from chat.tools.context_tools import (
    CONTEXT_TOOLS,
    CONTEXT_TOOL_NAMES,
    execute_get_guidance,
)
from chat.tools.graph_tools import GRAPH_TOOLS, GraphToolExecutor
# 新向量记忆系统
from chat.tools.vector_memory_tools import VECTOR_MEMORY_TOOLS, VECTOR_MEMORY_TOOL_NAMES
from chat.tools.vector_memory_executor import VectorMemoryExecutor
from memory.retriever import MemoryRetriever, format_memories_for_prompt

from chat.tools.quiz_generation_tools import QUIZ_GENERATION_TOOLS, QuizGenerationToolExecutor
from chat.tools.quiz_result_tools import QUIZ_RESULT_TOOLS, QUIZ_RESULT_TOOL_NAMES, QuizResultToolExecutor
from chat.tools.rag_tools import RAG_TOOLS, RAGToolExecutor
from rag.retrieval import get_search_service
from chat.tools.base import ToolResult
from chat.tools.client_tool_bridge import create_pending_request, wait_for_result
from chat.tools.schedule_tools import SCHEDULE_TOOLS
from chat.tools.web_tools import WEB_TOOLS, WebToolExecutor
from chat.tools.search_tools import SEARCH_TOOLS, SEARCH_TOOL_NAMES, SearchToolExecutor
from chat.tools.time_tools import TIME_TOOLS, TIME_TOOL_NAMES, TimeToolExecutor
from chat.tools.review_tools import REVIEW_TOOLS, REVIEW_TOOL_NAMES, ReviewToolExecutor
from chat.tools.agent_todo_tools import (
    AGENT_TODO_TOOLS,
    AGENT_TODO_TOOL_NAMES,
    AgentTodoToolExecutor,
)
from chat.tools.note_tools import NOTE_TOOL_NAMES, NoteToolExecutor
from chat.tools.artifact_tools import ARTIFACT_TOOL_NAMES, ArtifactToolExecutor
from chat.tools.image_tools import IMAGE_TOOLS, IMAGE_TOOL_NAMES, ImageToolExecutor
from chat.tools.code_sandbox_tools import CODE_SANDBOX_TOOLS, CODE_SANDBOX_TOOL_NAMES, CodeSandboxExecutor
from chat.tools.annotation_tools import ANNOTATION_TOOLS, ANNOTATION_TOOL_NAMES, AnnotationToolExecutor
from chat.tools.kb_tools import KB_TOOL_NAMES, KBToolExecutor
from review.service import get_due_reviews_count_by_space
from notes.service import NoteService
from notes.schemas import NoteCreate
from graph.service import GraphService
from db.database import get_scoped_session
from config import get_settings
from chat.streaming_cache import (
    init_streaming_cache,
    update_streaming_cache,
    clear_streaming_cache,
)

logger = logging.getLogger(__name__)

# Maximum tool calling iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 10


def _format_llm_error_message(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "AI 服务响应超时，请稍后重试"
    if isinstance(exc, httpx.ConnectError | httpx.RemoteProtocolError):
        return "AI 服务连接不稳定，请稍后重试"
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code in {400, 413, 422}:
            return "AI 请求内容过大或格式异常，请减少上下文后重试"
        if status_code in {401, 403}:
            return "AI 服务鉴权失败，请联系管理员检查服务配置"
        if status_code == 429:
            return "AI 服务请求过于频繁，请稍后重试"
        if status_code >= 500:
            return "AI 服务暂时繁忙，请稍后重试"
    return "AI 服务暂时不可用，请稍后重试"


def _truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}\n[结果已压缩，原始长度 {len(value)} 字符]"


def _sanitize_tool_value(value: Any, *, string_limit: int = 6000) -> Any:
    if isinstance(value, str):
        if value.startswith("data:image"):
            return f"[图片数据已省略，原始长度 {len(value)} 字符]"
        return _truncate_text(value, string_limit)
    if isinstance(value, list):
        max_items = 30
        items = [
            _sanitize_tool_value(item, string_limit=max(1000, string_limit // 2))
            for item in value[:max_items]
        ]
        if len(value) > max_items:
            items.append({"compressed": True, "omitted_items": len(value) - max_items})
        return items
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if "base64" in key_text or key_text in {"image_bytes", "file_bytes"}:
                sanitized[key] = f"[二进制数据已省略，原始长度 {len(str(item))} 字符]"
                continue
            sanitized[key] = _sanitize_tool_value(
                item,
                string_limit=max(1000, string_limit // 2),
            )
        return sanitized
    return value


def _tool_result_payload_for_llm(
    tool_name: str,
    tool_result: ToolResult,
    conversation_id: UUID,
) -> dict[str, Any]:
    settings = get_settings()
    max_chars = max(1000, int(settings.llm_tool_result_max_chars))
    payload = {
        "success": tool_result.success,
        "data": _sanitize_tool_value(tool_result.data),
        "message": tool_result.message,
    }
    serialized = json.dumps(payload, ensure_ascii=False, default=str)
    original_chars = len(serialized)
    compressed = False
    if original_chars > max_chars:
        preview_chars = max(500, max_chars - 500)
        payload = {
            "success": tool_result.success,
            "data": {
                "compressed": True,
                "original_chars": original_chars,
                "preview": _truncate_text(serialized, preview_chars),
            },
            "message": f"{tool_result.message}\n[系统提示] 工具结果已压缩，请基于预览继续；如需更多细节请缩小范围再次调用工具。",
        }
        compressed = True
        serialized = json.dumps(payload, ensure_ascii=False, default=str)

    logger.info(
        "[LLMToolResult] conversation_id=%s tool=%s tool_result_chars=%d compressed=%s",
        conversation_id,
        tool_name,
        len(serialized),
        compressed,
    )
    return payload


def _llm_context(context_collector: LLMContextCollector) -> dict[str, Any]:
    settings = get_settings()
    return context_collector.to_dict(max_chars=int(settings.llm_context_max_chars))


class SSEEventType:
    """SSE Event types for streaming responses"""

    TEXT_DELTA = "text_delta"  # Incremental text content
    THINKING_DELTA = "thinking_delta"  # Thinking/reasoning content from thinking models
    TOOL_CALL = "tool_call"  # Tool call status
    CLIENT_TOOL_REQUEST = "client_tool_request"  # Client-side tool request
    DONE = "done"  # Completion signal
    ERROR = "error"  # Error signal


class LLMOrchestrator:
    """
    Orchestrate LLM calls with multi-turn tool execution.

    Does NOT hold a DB session. Tool executors create short-lived sessions as needed.

    Responsible for:
    - Building system prompts
    - Managing LLM conversation loop
    - Dispatching and executing tool calls
    - Emitting SSE events for streaming responses
    """

    def __init__(
        self,
        user_id: UUID,
        conversation_id: UUID,
        space_id: UUID,
        space_name: str,
        previous_conversation_context: str | None = None,
        llm_model: str | None = None,
        search_channels: dict[str, bool] | None = None,
        tool_mode: str = "auto",
        enabled_tools: list[str] | None = None,
        has_panel_screenshot: bool = False,
        is_collaborative: bool = False,
        can_edit_graph: bool = False,
        max_output_tokens: int = 65536,
        enable_thinking: bool | None = None,
    ) -> None:
        """
        Initialize the orchestrator.

        Args:
            user_id: Current user ID
            conversation_id: Current conversation ID
            space_id: Learning space ID
            space_name: Learning space name
            previous_conversation_context: Previous conversation context for continuity (optional)
            llm_model: DashScope model ID override (resolved from model_id)
            search_channels: User's search channel settings (channel_name -> enabled)
            tool_mode: "auto" (AI按需加载) or "manual" (用户自选)
            enabled_tools: manual 模式下启用的工具名称列表
            is_collaborative: Whether this is a collaborative space
            can_edit_graph: Whether user can modify knowledge graph structure
            max_output_tokens: Maximum output tokens for LLM calls
            enable_thinking: Enable deep thinking mode (True=on, False=off, None=default/on)
        """
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.space_id = space_id
        self._metering_run_id = uuid4().hex
        self.space_name = space_name
        self.previous_conversation_context = previous_conversation_context
        self.enable_thinking = enable_thinking
        self.max_output_tokens = max_output_tokens
        self.tool_mode = tool_mode
        self.is_collaborative = is_collaborative

        # Initialize components
        self.settings = get_settings()
        self.llm_client = LLMClient(
            model_override=llm_model or self.settings.llm_default_model
        )
        self.prompt_builder = PromptBuilder()

        # 所有执行器始终初始化（自动模式下工具定义延迟加载，但执行器预先就位）
        self.graph_tool_executor = GraphToolExecutor(space_id, user_id=user_id, is_collaborative=is_collaborative, can_edit_graph=can_edit_graph)
        self.quiz_tool_executor = QuizGenerationToolExecutor(
            user_id, conversation_id, space_id
        )
        self.quiz_result_executor = QuizResultToolExecutor(user_id, space_id)
        self.web_tool_executor = WebToolExecutor()
        self.rag_tool_executor = RAGToolExecutor(space_id)
        self.time_tool_executor = TimeToolExecutor()
        self.review_tool_executor = ReviewToolExecutor(user_id, space_id)
        self.agent_todo_executor = AgentTodoToolExecutor(user_id, conversation_id)

        # 笔记工具
        self.note_tool_executor = NoteToolExecutor(user_id, space_id)

        # Artifact 工具
        self.artifact_tool_executor = ArtifactToolExecutor(user_id, space_id, conversation_id)

        # 图片生成工具
        self.image_tool_executor = ImageToolExecutor()

        # 代码沙箱工具
        self.code_sandbox_executor = CodeSandboxExecutor()

        # 新向量记忆系统（统一处理长期记忆和空间记忆）
        self.vector_memory_executor = VectorMemoryExecutor(user_id, space_id)
        self.memory_retriever = MemoryRetriever(user_id, space_id)

        # Citation registry for source attribution
        self._citation_registry: list[dict] = []

        # Context futures (populated in process_message for auto mode)
        self._context_futures: ContextFutures | None = None

        # Search channels: default all enabled
        self._search_channels = search_channels or {
            "web_search_enabled": True,
            "academic_search_enabled": True,
            "encyclopedia_search_enabled": True,
            "course_search_enabled": True,
        }

        # Initialize search tool executor
        channel_to_tool = {
            "academic_search_enabled": "academic_search",
            "encyclopedia_search_enabled": "encyclopedia_search",
            "course_search_enabled": "course_search",
        }
        any_search_enabled = any(
            self._search_channels.get(k, True) for k in channel_to_tool
        )
        self.search_tool_executor = SearchToolExecutor() if any_search_enabled else None
        self._search_tool_names = SEARCH_TOOL_NAMES

        # Tool name to executor mapping (used for dispatch regardless of mode)
        self._quiz_tool_names = {"generate_test"}
        self._quiz_result_tool_names = QUIZ_RESULT_TOOL_NAMES
        self._web_tool_names = {"web_search", "web_fetch", "web_crawl"}
        self._schedule_tool_names = {"get_schedule", "add_schedule", "delete_schedule", "update_schedule"}
        self._rag_tool_names = {"search_keywords", "search_regex", "list_documents", "read_document"}
        self._vector_memory_tool_names = VECTOR_MEMORY_TOOL_NAMES
        self._time_tool_names = TIME_TOOL_NAMES
        self._review_tool_names = REVIEW_TOOL_NAMES
        self._agent_todo_tool_names = AGENT_TODO_TOOL_NAMES
        self._note_tool_names = NOTE_TOOL_NAMES
        self._artifact_tool_names = ARTIFACT_TOOL_NAMES
        self._image_tool_names = IMAGE_TOOL_NAMES
        self._code_sandbox_tool_names = CODE_SANDBOX_TOOL_NAMES
        self._kb_tool_names = KB_TOOL_NAMES
        self.kb_tool_executor = KBToolExecutor(user_id, space_id)

        # Annotation tool (dual-sync mode)
        self._has_panel_screenshot = has_panel_screenshot
        self._annotation_tool_names = ANNOTATION_TOOL_NAMES
        self.annotation_executor = AnnotationToolExecutor()

        # 根据模式初始化 available_tools
        if tool_mode == "manual":
            # 手动模式：直接注册用户选择的工具完整定义
            self.available_tools = get_tools_for_manual_mode(
                enabled_tools, self._search_channels
            )
            self._tool_catalog_text = None
        else:
            # 自动模式：注册元工具 + 上下文工具
            self.available_tools = [GET_TOOL_DETAILS_TOOL] + list(CONTEXT_TOOLS)
            self._tool_catalog_text = format_catalog_for_prompt()

        # Add annotation tools when dual-sync mode is active
        if has_panel_screenshot:
            self.available_tools = list(self.available_tools) + ANNOTATION_TOOLS

    async def _auto_save_image_as_note(
        self,
        image_url: str,
        description: str,
        prompt: str,
        image_bytes: bytes,
        node_label: str | None,
        title: str | None = None,
    ) -> dict | None:
        """Auto-save a generated image as a note with attachment.

        Returns dict with note_id/note_title on success, None on failure.
        """
        note_title = title or ((prompt[:47] + "...") if len(prompt) > 50 else prompt)
        node_id = None

        # Phase 1: Create note
        try:
            async with get_scoped_session() as session:
                if node_label and node_label.upper() != "FREE":
                    graph_svc = GraphService(session)
                    node = await graph_svc.get_node_by_label(self.space_id, node_label)
                    if node:
                        node_id = node.id

                note_svc = NoteService(session)
                note_resp = await note_svc.create_note(
                    self.user_id,
                    self.space_id,
                    NoteCreate(
                        title=note_title,
                        content=None,
                        node_id=node_id,
                    ),
                )
            logger.info("Auto-saved image as note %s in space %s", note_resp.id, self.space_id)
        except Exception:
            logger.warning("Failed to create note for chart auto-save", exc_info=True)
            return None

        # Phase 2: Add attachment (separate session to avoid state leaks)
        try:
            async with get_scoped_session() as session:
                note_svc = NoteService(session)
                await note_svc.add_attachment(
                    self.user_id,
                    self.space_id,
                    note_resp.id,
                    file_data=image_bytes,
                    original_filename="generated-image.png",
                    mime_type="image/png",
                )
            logger.info("Added image attachment to note %s", note_resp.id)
        except Exception:
            logger.warning("Failed to add attachment to note %s", note_resp.id, exc_info=True)

        # Return note info regardless of attachment success
        result = {"note_id": str(note_resp.id), "note_title": note_title}
        if node_id:
            result["node_label"] = node_label
        return result

    async def _auto_save_code_result_as_note(
        self,
        code: str,
        stdout: str,
        description: str,
        image_url: str | None = None,
        image_bytes: bytes | None = None,
    ) -> dict | None:
        """Auto-save a code sandbox execution result as a note.

        Returns dict with note_id/note_title on success, None on failure.
        """
        # Guard: skip if no meaningful output
        if not stdout.strip() and not image_url:
            return None

        # Build title
        if description:
            note_title = (description[:47] + "...") if len(description) > 50 else description
        else:
            note_title = "Python 代码执行结果"

        # Build Markdown content
        parts = []

        # Code block (truncate to 100 lines)
        code_lines = code.split("\n")
        if len(code_lines) > 100:
            code_text = "\n".join(code_lines[:100]) + "\n# ...（代码已截断，共 {} 行）".format(len(code_lines))
        else:
            code_text = code
        parts.append(f"```python\n{code_text}\n```")

        # Stdout (truncate to 200 lines)
        if stdout.strip():
            stdout_lines = stdout.split("\n")
            if len(stdout_lines) > 200:
                stdout_text = "\n".join(stdout_lines[:200]) + "\n...（输出已截断，共 {} 行）".format(len(stdout_lines))
            else:
                stdout_text = stdout
            parts.append(f"**输出:**\n```\n{stdout_text}\n```")

        # Image reference
        if image_url:
            parts.append(f"**生成图像:**\n![代码输出图像]({image_url})")

        content = "\n\n".join(parts)

        # Phase 1: Create note
        try:
            async with get_scoped_session() as session:
                note_svc = NoteService(session)
                note_resp = await note_svc.create_note(
                    self.user_id,
                    self.space_id,
                    NoteCreate(title=note_title, content=content),
                )
            logger.info("Auto-saved code result as note %s in space %s", note_resp.id, self.space_id)
        except Exception:
            logger.warning("Failed to create note for code result auto-save", exc_info=True)
            return None

        # Phase 2: Add image attachment if available
        if image_bytes:
            try:
                async with get_scoped_session() as session:
                    note_svc = NoteService(session)
                    await note_svc.add_attachment(
                        self.user_id,
                        self.space_id,
                        note_resp.id,
                        file_data=image_bytes,
                        original_filename="code_output.png",
                        mime_type="image/png",
                    )
                logger.info("Added code output image to note %s", note_resp.id)
            except Exception:
                logger.warning("Failed to add image attachment to note %s", note_resp.id, exc_info=True)

        return {"note_id": str(note_resp.id), "note_title": note_title}

    async def _pre_retrieve_rag_context(self, query: str) -> tuple[str | None, list[dict]]:
        """自动 RAG 预检索，返回 (格式化的文档上下文, citations列表)。

        在 process_message 中与记忆检索并发执行，不增加延迟。
        失败时静默降级，不影响正常对话。
        """
        settings = get_settings()
        if not settings.rag_auto_inject_enabled:
            return None, []
        if should_skip_auto_rag(query):
            logger.info("Auto RAG skipped for generic follow-up query: %s", query[:50])
            return None, []

        try:
            async with get_scoped_session() as db:
                search_service = get_search_service(db)
                results = await search_service.search(
                    query=query,
                    space_id=self.space_id,
                    top_k=3,
                    score_threshold=settings.rag_auto_inject_threshold,
                )
            filtered_results = filter_auto_rag_results(
                results,
                score_threshold=settings.rag_auto_inject_threshold,
                max_results=3,
            )
            if len(filtered_results) != len(results):
                logger.info(
                    "Auto RAG filtered %d/%d candidates for query: %s",
                    len(results) - len(filtered_results),
                    len(results),
                    query[:50],
                )
            results = filtered_results
            if not results:
                return None, []
            lines = []
            citations = []
            for i, r in enumerate(results, start=1):
                source = r.document_title or r.document_filename or "未知文档"
                page_number = (r.metadata or {}).get("page_number")
                page_info = f"(第{page_number}页)" if page_number else ""
                lines.append(f"[{i}] 《{source}》{page_info}\n{r.content}")
                citations.append({
                    "index": i,
                    "source_type": "document",
                    "document_id": str(r.document_id),
                    "chunk_id": str(r.chunk_id),
                    "title": source,
                    "url": None,
                    "page_number": page_number,
                    "content": r.content,
                    "snippet": r.content[:100],
                    "score": round(
                        r.rerank_score if r.rerank_score is not None
                        else (r.retrieval_score if r.retrieval_score is not None else r.score),
                        3,
                    ),
                    "retrieval_score": (
                        round(r.retrieval_score, 3)
                        if r.retrieval_score is not None else None
                    ),
                    "rerank_score": (
                        round(r.rerank_score, 3)
                        if r.rerank_score is not None else None
                    ),
                    "retrieval_source": r.retrieval_source,
                })
            return "\n\n---\n\n".join(lines), citations
        except Exception as e:
            logger.warning(f"RAG auto-inject failed: {e}")
            return None, []

    _CITABLE_TOOLS = {"search_keywords", "web_search", "web_crawl", "academic_search", "encyclopedia_search"}

    @staticmethod
    def _get_source_type(tool_name: str) -> str:
        return {
            "search_keywords": "document",
            "web_search": "web",
            "web_crawl": "web",
            "academic_search": "academic",
            "encyclopedia_search": "encyclopedia",
        }.get(tool_name, "unknown")

    def _register_tool_citations(self, tool_call: ToolCall, tool_result: ToolResult) -> None:
        """Register citations from citable tool results."""
        if tool_call.name not in self._CITABLE_TOOLS:
            return
        if not tool_result.success or not tool_result.data:
            return
        # Build set of existing chunk_ids for deduplication
        existing_chunk_ids = {
            c.get("chunk_id") for c in self._citation_registry if c.get("chunk_id")
        }
        results = tool_result.data.get("results", [])
        for r in results:
            chunk_id = r.get("chunk_id")
            if chunk_id and chunk_id in existing_chunk_ids:
                continue
            # Use retrieval_score (cosine similarity) for display, not RRF score
            quality_score = r.get("retrieval_score") or r.get("rerank_score") or r.get("score") or 0
            if quality_score < 0.4:
                continue
            idx = len(self._citation_registry) + 1
            citation = {
                "index": idx,
                "source_type": self._get_source_type(tool_call.name),
                "title": r.get("title") or r.get("source") or "未知来源",
                "url": r.get("url"),
                "content": r.get("content") or r.get("snippet", ""),
                "snippet": (r.get("content") or r.get("snippet", ""))[:100],
                "score": quality_score,
                "document_id": r.get("document_id"),
                "chunk_id": chunk_id,
                "page_number": r.get("page_number"),
            }
            self._citation_registry.append(citation)
            if chunk_id:
                existing_chunk_ids.add(chunk_id)

    async def process_message(
        self,
        user_message: str | dict[str, Any],
        history_messages: list[dict[str, str]],
        current_message_image_urls: list[str] | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process user message and yield SSE events.

        Args:
            user_message: The current user message (str or multimodal dict)
            history_messages: Previous conversation messages

        Yields:
            SSE events in format:
            - {"event": "text_delta", "data": {"content": "..."}}
            - {"event": "tool_call", "data": {"tool": "...", "status": "running|done", ...}}
            - {"event": "done", "data": {"content": "full response"}}
            - {"event": "error", "data": {"message": "..."}}
        """
        t_orch_start = time.monotonic()

        # Initialize streaming cache for resume support
        await init_streaming_cache(str(self.conversation_id))

        # 1. 提取用户消息文本用于语义检索
        if isinstance(user_message, str):
            message_text = user_message
        else:
            # 多模态消息：提取文本内容
            content = user_message.get("content", "")
            if isinstance(content, list):
                message_text = " ".join(
                    c.get("text", "") for c in content if c.get("type") == "text"
                )
            else:
                message_text = str(content)

        # 2. Context retrieval: async fire-and-forget for memory/RAG, sync for reviews_count
        t0 = time.monotonic()
        settings = get_settings()

        if self.tool_mode == "auto" and settings.context_tools_enabled:
            # Auto mode: launch memory + RAG in background, only await reviews_count (fast DB query).
            # RAG reranker's CPU-bound work runs in asyncio.to_thread() so it won't block the event loop.
            reviews_count, agent_todo_prompt = await asyncio.gather(
                get_due_reviews_count_by_space(self.user_id, self.space_id),
                get_agent_todo_prompt_state(self.user_id, self.conversation_id),
            )
            self._context_futures = ContextFutures(
                memory_task=asyncio.create_task(
                    self.memory_retriever.get_relevant_memories(
                        user_message=message_text, max_long_term=5, max_space=5,
                    )
                ),
                rag_task=asyncio.create_task(
                    self._pre_retrieve_rag_context(message_text)
                ),
                previous_context=self.previous_conversation_context,
            )
            logger.info(f"[Perf] Reviews query + tasks launched: {(time.monotonic()-t0)*1000:.0f}ms")

            # Build minimal system prompt (no memories, RAG, or previous context)
            t0 = time.monotonic()
            system_prompt = self.prompt_builder.build_base_system_prompt(
                space_id=self.space_id,
                space_name=self.space_name,
                reviews_count=reviews_count,
                tool_catalog=self._tool_catalog_text,
                has_panel_screenshot=self._has_panel_screenshot,
                agent_todos=agent_todo_prompt,
            )
            logger.info(f"[Perf] Build base prompt ({len(system_prompt)} chars): {(time.monotonic()-t0)*1000:.0f}ms")
        else:
            # Manual mode / context_tools disabled: original synchronous flow
            self._context_futures = None
            relevant_memories, reviews_count, rag_result, agent_todo_prompt = await asyncio.gather(
                self.memory_retriever.get_relevant_memories(
                    user_message=message_text, max_long_term=5, max_space=5,
                ),
                get_due_reviews_count_by_space(self.user_id, self.space_id),
                self._pre_retrieve_rag_context(message_text),
                get_agent_todo_prompt_state(self.user_id, self.conversation_id),
            )
            rag_context, rag_citations = rag_result
            self._citation_registry = rag_citations
            logger.info(f"[Perf] Memory + reviews + RAG retrieval: {(time.monotonic()-t0)*1000:.0f}ms")

            formatted_memories = format_memories_for_prompt(
                relevant_memories, current_space_id=self.space_id
            )

            t0 = time.monotonic()
            system_prompt = self.prompt_builder.build_system_prompt(
                space_id=self.space_id,
                space_name=self.space_name,
                relevant_memories=formatted_memories,
                previous_conversation_context=self.previous_conversation_context,
                reviews_count=reviews_count,
                tool_catalog=self._tool_catalog_text,
                has_panel_screenshot=self._has_panel_screenshot,
                rag_context=rag_context,
                agent_todos=agent_todo_prompt,
            )
            logger.info(f"[Perf] Build prompt ({len(system_prompt)} chars): {(time.monotonic()-t0)*1000:.0f}ms")

        # Handle both string and dict formats for user message
        if isinstance(user_message, str):
            current_user_message = {"role": "user", "content": user_message}
        else:
            # Already in dict format (multimodal message)
            current_user_message = user_message
        current_message_image_urls = list(current_message_image_urls or [])

        # 2. Build messages array
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *history_messages,
            current_user_message,
        ]

        total_chars = sum(len(str(m.get('content', ''))) for m in messages)
        logger.info(f"[Perf] Messages: {len(messages)} msgs, ~{total_chars} chars")
        logger.info(f"[Perf] Tools: {len(self.available_tools)} tools")
        logger.info(f"[Perf] Orchestrator prep: {(time.monotonic()-t_orch_start)*1000:.0f}ms")

        # 3. Initialize LLM context collector for feedback/debugging
        context_collector = LLMContextCollector(
            model=self.llm_client.model,
            initial_messages=copy.deepcopy(messages),
            tools=copy.deepcopy(self.available_tools),
            temperature=0.7,
            max_tokens=self.max_output_tokens,
        )

        # 4. Multi-turn tool calling loop with streaming
        full_response = ""
        # Accumulate token usage across iterations
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_charge_cents = 0

        for iteration in range(MAX_TOOL_ITERATIONS):
            logger.debug(f"LLM iteration {iteration + 1}/{MAX_TOOL_ITERATIONS}")

            pending_tool_calls: list[ToolCall] = []
            iteration_content = ""
            finish_reason = None
            current_iteration = IterationData()
            t_llm_start = time.monotonic()
            first_token_logged = False

            try:
                # Use streaming method for real-time text output
                async for event in stream_tool_completion(
                    self.llm_client,
                    messages=messages,
                    tools=self.available_tools,
                    temperature=0.7,
                    max_tokens=self.max_output_tokens,
                    enable_thinking=self.enable_thinking,
                    usage_context=UsageContext(
                        user_id=self.user_id,
                        usage_type=UsageType.CHAT_LLM,
                        source_module="chat",
                        source_operation="space_chat",
                        billable=True,
                        space_id=self.space_id,
                        conversation_id=self.conversation_id,
                    ),
                    idempotency_key=f"space_chat:{self.conversation_id}:{self._metering_run_id}:{iteration}",
                ):
                    event_type = event.get("type")

                    # Emit thinking content (reasoning models)
                    if event_type == "thinking":
                        if not first_token_logged:
                            logger.info(f"[Perf] LLM first token (thinking): {(time.monotonic()-t_llm_start)*1000:.0f}ms")
                            first_token_logged = True
                        current_iteration.reasoning_content += event["content"]
                        yield {
                            "event": SSEEventType.THINKING_DELTA,
                            "data": {"content": event["content"]},
                        }
                        # Update streaming cache for resume support
                        await update_streaming_cache(
                            str(self.conversation_id),
                            thinking_delta=event["content"],
                        )

                    # Immediately emit text content as it arrives
                    elif event_type == "content":
                        if not first_token_logged:
                            logger.info(f"[Perf] LLM first token: {(time.monotonic()-t_llm_start)*1000:.0f}ms")
                            first_token_logged = True
                        content = event["content"]
                        iteration_content += content
                        full_response += content
                        current_iteration.content += content
                        yield {
                            "event": SSEEventType.TEXT_DELTA,
                            "data": {"content": content},
                        }
                        # Update streaming cache for resume support
                        await update_streaming_cache(
                            str(self.conversation_id),
                            content_delta=content,
                        )

                    # Tool call started - emit running status
                    elif event_type == "tool_call_start":
                        yield {
                            "event": SSEEventType.TOOL_CALL,
                            "data": {
                                "id": event["id"],
                                "tool": event["name"],
                                "status": "running",
                            },
                        }

                    # Tool call complete - collect for execution
                    elif event_type == "tool_call_end":
                        pending_tool_calls.append(ToolCall(
                            id=event["id"],
                            name=event["name"],
                            arguments=event["arguments"]
                        ))
                        # Collect tool call for context
                        if current_iteration.tool_calls is None:
                            current_iteration.tool_calls = []
                        current_iteration.tool_calls.append({
                            "id": event["id"],
                            "name": event["name"],
                            "arguments": event["arguments"],
                        })

                    # Stream finished
                    elif event_type == "done":
                        finish_reason = event["finish_reason"]
                        # Accumulate token usage if available
                        usage = event.get("usage")
                        if usage:
                            total_prompt_tokens += usage.get("prompt_tokens", 0)
                            total_completion_tokens += usage.get("completion_tokens", 0)
                        billing = event.get("billing")
                        if billing:
                            total_charge_cents += billing.get("charge_cents", 0) or 0

            except Exception as e:
                logger.error(f"LLM call failed: {e}", exc_info=True)
                yield {
                    "event": SSEEventType.ERROR,
                    "data": {"message": _format_llm_error_message(e)},
                }
                return

            # Execute pending tool calls
            if pending_tool_calls:
                tool_results_for_context: list[tuple[ToolCall, ToolResult, dict[str, Any]]] = []

                for tool_call in pending_tool_calls:
                    # Execute tool - dispatch to appropriate executor

                    # --- Context tools (async retrieval via ContextFutures) ---
                    if tool_call.name == "get_context_memories" and self._context_futures:
                        tool_result = await self._context_futures.get_memories(self.space_id)
                    elif tool_call.name == "get_context_documents" and self._context_futures:
                        tool_result = await self._context_futures.get_documents()
                        if tool_result.success and tool_result.data:
                            self._citation_registry = tool_result.data.get("citations", [])
                    elif tool_call.name == "get_previous_context" and self._context_futures:
                        tool_result = self._context_futures.get_previous_context()
                    elif tool_call.name == "get_guidance":
                        topics = tool_call.arguments.get("topics", [])
                        tool_result = execute_get_guidance(topics)

                    # --- Meta tool: get_tool_details ---
                    elif tool_call.name == "get_tool_details":
                        # 自动模式元工具：返回工具 schema + 动态追加工具定义
                        requested_names = tool_call.arguments.get("tool_names", [])
                        tool_result, new_tools = execute_get_tool_details(
                            requested_names,
                            self.available_tools,
                            self._search_channels,
                        )
                        if new_tools:
                            self.available_tools = list(self.available_tools) + new_tools
                    elif tool_call.name in self._quiz_tool_names:
                        tool_result = await self.quiz_tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                    elif tool_call.name in self._quiz_result_tool_names:
                        tool_result = await self.quiz_result_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                    elif tool_call.name in self._web_tool_names:
                        tool_result = await self.web_tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                    elif tool_call.name in self._schedule_tool_names:
                        # Client-side tool: delegate to frontend via SSE
                        await create_pending_request(
                            self.conversation_id,
                            tool_call.id,
                            tool_call.name,
                            tool_call.arguments,
                        )
                        yield {
                            "event": SSEEventType.CLIENT_TOOL_REQUEST,
                            "data": {
                                "tool_call_id": tool_call.id,
                                "tool": tool_call.name,
                                "params": tool_call.arguments,
                            },
                        }
                        # Wait for frontend to POST result back (up to 60s)
                        tool_result = await wait_for_result(
                            tool_call.id, timeout=60.0
                        )
                    elif tool_call.name in self._rag_tool_names:
                        tool_result = await self.rag_tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                    elif tool_call.name in self._vector_memory_tool_names:
                        tool_result = await self.vector_memory_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                    elif tool_call.name in self._time_tool_names:
                        tool_result = await self.time_tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                    elif tool_call.name in self._agent_todo_tool_names:
                        tool_result = await self.agent_todo_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                    elif tool_call.name in self._review_tool_names:
                        tool_result = await self.review_tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                    elif tool_call.name in self._search_tool_names and self.search_tool_executor:
                        tool_result = await self.search_tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                    elif tool_call.name in self._image_tool_names:
                        tool_result = await self.image_tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                            reference_image_urls=current_message_image_urls,
                        )
                        # Auto-save image as note
                        if tool_result.success and tool_result.data and tool_result.image_base64:
                            import base64 as _b64
                            note_info = await self._auto_save_image_as_note(
                                image_url=tool_result.data.get("image_url", ""),
                                description=tool_result.data.get("description", ""),
                                prompt=tool_call.arguments.get("description", ""),
                                image_bytes=_b64.b64decode(tool_result.image_base64),
                                node_label=tool_call.arguments.get("node_label"),
                                title=tool_call.arguments.get("title"),
                            )
                            if note_info:
                                tool_result.data["note_id"] = note_info["note_id"]
                                tool_result.data["note_title"] = note_info["note_title"]
                                tool_result.data["auto_saved"] = True
                                if note_info.get("node_label"):
                                    tool_result.data["node_label"] = note_info["node_label"]
                    elif tool_call.name in self._artifact_tool_names:
                        tool_result = await self.artifact_tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                    elif tool_call.name in self._code_sandbox_tool_names:
                        tool_result = await self.code_sandbox_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                        # Auto-save code result as note
                        if tool_result.success and tool_result.data:
                            _stdout = tool_result.data.get("stdout", "")
                            _img_url = tool_result.data.get("image_url")
                            if _stdout.strip() or _img_url:
                                import base64 as _b64
                                _img_bytes = (
                                    _b64.b64decode(tool_result.image_base64)
                                    if tool_result.image_base64
                                    else None
                                )
                                note_info = await self._auto_save_code_result_as_note(
                                    code=tool_call.arguments.get("code", ""),
                                    stdout=_stdout,
                                    description=tool_call.arguments.get("description", ""),
                                    image_url=_img_url,
                                    image_bytes=_img_bytes,
                                )
                                if note_info:
                                    tool_result.data["note_id"] = note_info["note_id"]
                                    tool_result.data["note_title"] = note_info["note_title"]
                                    tool_result.data["auto_saved"] = True
                    elif tool_call.name in self._note_tool_names:
                        if tool_call.name == "create_note":
                            # Require user confirmation before creating note
                            await create_pending_request(
                                self.conversation_id,
                                tool_call.id,
                                tool_call.name,
                                tool_call.arguments,
                            )
                            yield {
                                "event": SSEEventType.CLIENT_TOOL_REQUEST,
                                "data": {
                                    "tool_call_id": tool_call.id,
                                    "tool": tool_call.name,
                                    "params": tool_call.arguments,
                                },
                            }
                            confirmation = await wait_for_result(
                                tool_call.id, timeout=120.0
                            )
                            if confirmation.success:
                                # User confirmed — execute with (possibly modified) arguments
                                modified_args = (confirmation.data or {}).get(
                                    "arguments", tool_call.arguments
                                )
                                tool_call.arguments = modified_args
                                tool_result = await self.note_tool_executor.execute(
                                    tool_call.name, modified_args,
                                )
                            else:
                                tool_result = ToolResult(
                                    success=False,
                                    data=None,
                                    message=confirmation.message or "用户取消了笔记创建",
                                )
                        else:
                            # Other note tools (list, view, update, delete) — auto-execute
                            tool_result = await self.note_tool_executor.execute(
                                tool_call.name,
                                tool_call.arguments,
                            )
                    elif tool_call.name in self._kb_tool_names:
                        tool_result = await self.kb_tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                    elif tool_call.name in self._annotation_tool_names:
                        tool_result = await self.annotation_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                    else:
                        tool_result = await self.graph_tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )

                    # Store result for context
                    llm_tool_payload = _tool_result_payload_for_llm(
                        tool_call.name,
                        tool_result,
                        self.conversation_id,
                    )
                    tool_results_for_context.append((tool_call, tool_result, llm_tool_payload))

                    # Register citations from citable tool results
                    self._register_tool_citations(tool_call, tool_result)

                    # Collect tool result for LLM context
                    if current_iteration.tool_results is None:
                        current_iteration.tool_results = []
                    current_iteration.tool_results.append({
                        "tool_call_id": tool_call.id,
                        **llm_tool_payload,
                    })

                    # Emit tool_call done event
                    yield {
                        "event": SSEEventType.TOOL_CALL,
                        "data": {
                            "id": tool_call.id,
                            "tool": tool_call.name,
                            "status": "done",
                            "success": tool_result.success,
                            "result": tool_result.data,
                            "message": tool_result.message,
                            "arguments": tool_call.arguments,
                        },
                    }
                    await update_streaming_cache(
                        str(self.conversation_id),
                        tool_call={
                            "id": tool_call.id,
                            "tool": tool_call.name,
                            "status": "done",
                            "success": tool_result.success,
                            "result": tool_result.data,
                            "message": tool_result.message,
                            "arguments": tool_call.arguments,
                        },
                    )

                # Append current iteration to collector
                context_collector.iterations.append(current_iteration)

                # Add assistant message with tool calls to context
                # Note: Gemini 模型不接受 content: null，需要用空字符串代替
                messages.append(
                    {
                        "role": "assistant",
                        "content": iteration_content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(
                                        tc.arguments, ensure_ascii=False
                                    ),
                                },
                            }
                            for tc in pending_tool_calls
                        ],
                    }
                )

                # Add tool results to context
                for tool_call, _tool_result, llm_tool_payload in tool_results_for_context:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(llm_tool_payload, ensure_ascii=False),
                        }
                    )

                # Inject tool images as visual context for follow-up analysis
                image_parts = []
                for _tc, tr, _payload in tool_results_for_context:
                    if tr.image_base64:
                        image_parts.append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{tr.image_base64}"},
                        })
                if image_parts:
                    messages.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "[系统提示] 以上是工具渲染出的文档页面图片，请结合当前问题直接分析页面内容。"},
                            *image_parts,
                        ],
                    })

                # Fallback: inject unconsumed context into system prompt after iteration 0
                if (
                    iteration == 0
                    and self._context_futures
                    and not self._context_futures.all_consumed
                    and get_settings().context_fallback_injection
                ):
                    injection_parts = self._context_futures.try_collect_unconsumed(
                        current_space_id=self.space_id
                    )
                    if injection_parts:
                        # Append to system message (messages[0]) — NOT as a user message,
                        # to avoid the AI treating it as new input requiring extra tool calls.
                        messages[0]["content"] += "\n\n" + "\n\n".join(injection_parts)
                        logger.info(
                            "[ContextFutures] Fallback injection into system prompt: %d sections",
                            len(injection_parts),
                        )

                # Continue loop to let LLM process tool results
                continue

            # No tool calls - check if we're done
            if not pending_tool_calls and finish_reason == "tool_calls":
                logger.warning(
                    "LLM indicated tool_calls but no tool_call_end events received. "
                    "This may indicate a streaming format issue."
                )

            # Handle truncation: finish_reason="length" means max_tokens was hit
            # The model may have intended to call tools but got cut off
            if finish_reason == "length" and not pending_tool_calls and iteration_content:
                logger.warning(
                    "LLM response truncated (finish_reason=length), retrying with tool call hint. "
                    "iteration=%d, content_len=%d",
                    iteration + 1, len(iteration_content),
                )
                messages.append({"role": "assistant", "content": iteration_content})
                messages.append({
                    "role": "user",
                    "content": "[系统提示] 你的回复被截断了。请直接调用工具，不要用文字描述你将要做什么。",
                })
                continue

            if finish_reason == "stop" or not pending_tool_calls:
                # Append final iteration (no tool calls)
                if current_iteration.content:
                    context_collector.iterations.append(current_iteration)
                break

        # Finalize context collector
        context_collector.final_content = full_response
        context_collector.finish_reason = finish_reason or "stop"

        # Mark streaming cache as complete
        await update_streaming_cache(str(self.conversation_id), is_complete=True)

        # Emit done event with LLM context and citations
        yield {
            "event": SSEEventType.DONE,
            "data": {
                "content": full_response,
                "llm_context": _llm_context(context_collector),
                "citations": self._citation_registry if self._citation_registry else None,
                "usage": {
                    "prompt_tokens": total_prompt_tokens,
                    "completion_tokens": total_completion_tokens,
                    "total_tokens": total_prompt_tokens + total_completion_tokens,
                },
                "billing": {
                    "charge_cents": total_charge_cents,
                    "billing_status": "charged" if total_charge_cents > 0 else "not_charged",
                },
            },
        }

    # Note: 旧的 _load_long_term_memory 和 _load_space_memory 已被
    # MemoryRetriever.get_relevant_memories() 替代，使用语义检索而非全量加载
