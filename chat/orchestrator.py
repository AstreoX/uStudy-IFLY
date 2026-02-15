"""LLM Orchestrator - Multi-turn tool calling loop with SSE"""

import copy
import json
import logging
from typing import Any, AsyncGenerator
from uuid import UUID

from sqlalchemy import select

from agents.llm.client import OpenRouterClient, ToolCall
from usage.models import UsageType
from usage.recorder import schedule_usage_recording
from chat.context_collector import IterationData, LLMContextCollector
from chat.prompt_builder import PromptBuilder
from chat.tools.graph_tools import GRAPH_TOOLS, GraphToolExecutor
from chat.tools.learning_space_executor import LearningSpaceToolExecutor
from chat.tools.learning_space_tools import (
    LEARNING_SPACE_TOOLS,
    get_tool_metadata,
)
# 新向量记忆系统
from chat.tools.vector_memory_tools import VECTOR_MEMORY_TOOLS, VECTOR_MEMORY_TOOL_NAMES
from chat.tools.vector_memory_executor import VectorMemoryExecutor
from memory.retriever import MemoryRetriever, format_memories_for_prompt

# 旧记忆系统（仅 QuickChat 暂时保留，后续统一迁移）
from chat.tools.memory_tools import MEMORY_TOOLS, MEMORY_TOOL_NAMES
from chat.tools.memory_executor import MemoryToolExecutor, format_memory_for_prompt
from chat.tools.quiz_generation_tools import QUIZ_GENERATION_TOOLS, QuizGenerationToolExecutor
from chat.tools.rag_tools import RAG_TOOLS, RAGToolExecutor
from chat.tools.client_tool_bridge import create_pending_request, wait_for_result
from chat.tools.schedule_tools import SCHEDULE_TOOLS
from chat.tools.web_tools import WEB_TOOLS, WebToolExecutor
from chat.tools.time_tools import TIME_TOOLS, TIME_TOOL_NAMES, TimeToolExecutor
from db.database import get_scoped_session
from db.models import LongTermMemory
from config import get_settings

logger = logging.getLogger(__name__)

# Maximum tool calling iterations to prevent infinite loops
MAX_TOOL_ITERATIONS = 10
MAX_QUICK_CHAT_TOOL_ITERATIONS = 5  # Quick chat mode: max 5 iterations


class SSEEventType:
    """SSE Event types for streaming responses"""

    TEXT_DELTA = "text_delta"  # Incremental text content
    TOOL_CALL = "tool_call"  # Tool call status
    CLIENT_TOOL_REQUEST = "client_tool_request"  # Client-side tool request
    DONE = "done"  # Completion signal
    ERROR = "error"  # Error signal


class QuickChatOrchestrator:
    """
    Orchestrator for quick chat mode with learning space tools.

    Does NOT hold a DB session. Tool executors create short-lived sessions as needed.

    Supports:
    - view_learning_spaces: Auto-execute, view user's spaces
    - rebind_to_learning_space: Requires confirmation, bind to existing space
    - create_learning_space: Requires confirmation, create new space
    """

    def __init__(
        self,
        user_id: UUID,
        conversation_id: UUID,
        previous_conversation_context: str | None = None,
    ) -> None:
        """
        Initialize the quick chat orchestrator.

        Args:
            user_id: Current user ID
            conversation_id: Current conversation ID
            previous_conversation_context: Previous conversation context for continuity (optional)
        """
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.previous_conversation_context = previous_conversation_context

        self.settings = get_settings()
        self.llm_client = OpenRouterClient(
            model_override=self.settings.openrouter_model
        )
        self.prompt_builder = PromptBuilder()
        self.tool_executor = LearningSpaceToolExecutor(
            user_id, conversation_id
        )
        self.memory_tool_executor = MemoryToolExecutor(user_id)
        self.time_tool_executor = TimeToolExecutor()

        # Available tools for quick chat (learning space + memory + time)
        self.available_tools = LEARNING_SPACE_TOOLS + MEMORY_TOOLS + TIME_TOOLS

    async def process_message(
        self,
        user_message: str | dict[str, Any],
        history_messages: list[dict[str, str]],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process message with learning space tools support.

        Multi-turn tool calling loop allows AI to:
        1. Call view_learning_spaces to see available spaces
        2. See the result and decide to call rebind_to_learning_space

        Args:
            user_message: The current user message (str or multimodal dict)
            history_messages: Previous conversation messages

        Yields:
            SSE events for streaming response
        """
        # Load user's long-term memory
        long_term_memory = await self._load_long_term_memory()

        # Build system prompt with tool instructions, memory, and previous conversation context
        system_prompt = self.prompt_builder.build_quick_chat_prompt(
            with_tools=True,
            long_term_memory=long_term_memory,
            previous_conversation_context=self.previous_conversation_context,
        )

        # Handle both string and dict formats for user message
        if isinstance(user_message, str):
            current_user_message = {"role": "user", "content": user_message}
        else:
            # Already in dict format (multimodal message)
            current_user_message = user_message

        # Build messages
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *history_messages,
            current_user_message,
        ]

        # Initialize LLM context collector for feedback/debugging
        context_collector = LLMContextCollector(
            model=self.llm_client.model,
            initial_messages=copy.deepcopy(messages),
            tools=copy.deepcopy(self.available_tools),
            temperature=0.7,
            max_tokens=4096,
        )

        full_response = ""
        finish_reason = None
        # Accumulate token usage across iterations
        total_prompt_tokens = 0
        total_completion_tokens = 0

        # Multi-turn tool calling loop
        for iteration in range(MAX_QUICK_CHAT_TOOL_ITERATIONS):
            logger.debug(f"Quick chat iteration {iteration + 1}/{MAX_QUICK_CHAT_TOOL_ITERATIONS}")

            pending_tool_calls: list[ToolCall] = []
            iteration_content = ""
            has_confirmation_tool = False
            current_iteration = IterationData()

            try:
                async for event in self.llm_client.stream_complete_with_tools(
                    messages=messages,
                    tools=self.available_tools,
                    temperature=0.7,
                ):
                    event_type = event.get("type")

                    # Emit text content immediately
                    if event_type == "content":
                        content = event["content"]
                        iteration_content += content
                        full_response += content
                        current_iteration.content += content
                        yield {
                            "event": SSEEventType.TEXT_DELTA,
                            "data": {"content": content},
                        }

                    # Stream finished
                    elif event_type == "done":
                        finish_reason = event.get("finish_reason")
                        # Accumulate token usage if available
                        usage = event.get("usage")
                        logger.info(f"[QuickChat] Done event: finish_reason={finish_reason}, usage={usage}")
                        if usage:
                            total_prompt_tokens += usage.get("prompt_tokens", 0)
                            total_completion_tokens += usage.get("completion_tokens", 0)
                            logger.info(f"[QuickChat] Accumulated: prompt={total_prompt_tokens}, completion={total_completion_tokens}")

                    # Tool call started
                    elif event_type == "tool_call_start":
                        tool_name = event["name"]
                        metadata = get_tool_metadata(tool_name)

                        yield {
                            "event": SSEEventType.TOOL_CALL,
                            "data": {
                                "id": event["id"],
                                "tool": tool_name,
                                "status": "running",
                                "display_name": metadata["display_name"],
                                "requires_confirmation": metadata["requires_confirmation"],
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

            except Exception as e:
                logger.error(f"Quick chat LLM error: {e}", exc_info=True)
                yield {
                    "event": SSEEventType.ERROR,
                    "data": {"message": f"AI 服务暂时不可用: {str(e)}"},
                }
                return

            # No tool calls - we're done
            if not pending_tool_calls:
                break

            # Process tool calls
            tool_results_for_context: list[tuple[ToolCall, Any]] = []

            for tool_call in pending_tool_calls:
                metadata = get_tool_metadata(tool_call.name)

                if metadata["requires_confirmation"]:
                    # Emit pending_confirmation status - frontend will handle
                    has_confirmation_tool = True
                    yield {
                        "event": SSEEventType.TOOL_CALL,
                        "data": {
                            "id": tool_call.id,
                            "tool": tool_call.name,
                            "status": "pending_confirmation",
                            "arguments": tool_call.arguments,
                            "display_name": metadata["display_name"],
                            "requires_confirmation": True,
                        },
                    }
                else:
                    # Auto-execute tools that don't require confirmation
                    # Dispatch to appropriate executor
                    if tool_call.name in MEMORY_TOOL_NAMES:
                        tool_result = await self.memory_tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                    elif tool_call.name in TIME_TOOL_NAMES:
                        tool_result = await self.time_tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )
                    else:
                        tool_result = await self.tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )

                    tool_results_for_context.append((tool_call, tool_result))

                    # Collect tool result for LLM context
                    if current_iteration.tool_results is None:
                        current_iteration.tool_results = []
                    current_iteration.tool_results.append({
                        "tool_call_id": tool_call.id,
                        "success": tool_result.success,
                        "data": tool_result.data,
                        "message": tool_result.message,
                    })

                    yield {
                        "event": SSEEventType.TOOL_CALL,
                        "data": {
                            "id": tool_call.id,
                            "tool": tool_call.name,
                            "status": "done",
                            "success": tool_result.success,
                            "result": tool_result.data,
                            "message": tool_result.message,
                            "display_name": metadata["display_name"],
                            "requires_confirmation": False,
                        },
                    }

            # Append current iteration to collector
            context_collector.iterations.append(current_iteration)

            # If there's a confirmation-required tool, stop the loop
            # The frontend will handle the confirmation flow
            if has_confirmation_tool:
                break

            # If we have auto-executed tools, add results to context and continue
            if tool_results_for_context:
                # Add assistant message with tool calls to context
                messages.append({
                    "role": "assistant",
                    "content": iteration_content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc, _ in tool_results_for_context
                    ],
                })

                # Add tool results to context
                for tool_call, tool_result in tool_results_for_context:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result.to_dict(), ensure_ascii=False),
                    })

                # Continue to next iteration - AI can now see the tool results
                continue

            # No tools executed, break
            break

        # Finalize context collector
        context_collector.final_content = full_response
        context_collector.finish_reason = finish_reason or "stop"

        # Record API usage (fire-and-forget)
        logger.info(f"[QuickChat] Final usage check: prompt={total_prompt_tokens}, completion={total_completion_tokens}")
        if total_prompt_tokens > 0 or total_completion_tokens > 0:
            logger.info(f"[QuickChat] Recording usage: user={self.user_id}, model={self.llm_client.model}")
            schedule_usage_recording(
                user_id=self.user_id,
                usage_type=UsageType.QUICK_CHAT_LLM,
                model=self.llm_client.model,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                conversation_id=self.conversation_id,
            )
        else:
            logger.warning("[QuickChat] No usage to record - tokens are 0")

        yield {
            "event": SSEEventType.DONE,
            "data": {
                "content": full_response,
                "llm_context": context_collector.to_dict(),
            },
        }

    async def _load_long_term_memory(self) -> str:
        """Load user's long-term memory and format for prompt injection."""
        async with get_scoped_session() as db:
            result = await db.execute(
                select(LongTermMemory).where(LongTermMemory.user_id == self.user_id)
            )
            memory = result.scalar_one_or_none()

            if memory and memory.entries:
                return format_memory_for_prompt(memory.entries)
            return ""


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
    ) -> None:
        """
        Initialize the orchestrator.

        Args:
            user_id: Current user ID
            conversation_id: Current conversation ID
            space_id: Learning space ID
            space_name: Learning space name
            previous_conversation_context: Previous conversation context for continuity (optional)
        """
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.space_id = space_id
        self.space_name = space_name
        self.previous_conversation_context = previous_conversation_context

        # Initialize components
        self.settings = get_settings()
        self.llm_client = OpenRouterClient(
            model_override=self.settings.openrouter_model
        )
        self.prompt_builder = PromptBuilder()
        self.graph_tool_executor = GraphToolExecutor(space_id)
        self.quiz_tool_executor = QuizGenerationToolExecutor(
            user_id, conversation_id, space_id
        )
        self.web_tool_executor = WebToolExecutor()
        self.rag_tool_executor = RAGToolExecutor(space_id)
        self.time_tool_executor = TimeToolExecutor()

        # 新向量记忆系统（统一处理长期记忆和空间记忆）
        self.vector_memory_executor = VectorMemoryExecutor(user_id, space_id)
        self.memory_retriever = MemoryRetriever(user_id, space_id)

        # Combined tools list for learning space mode (using new vector memory tools)
        self.available_tools = (
            GRAPH_TOOLS
            + QUIZ_GENERATION_TOOLS
            + WEB_TOOLS
            + SCHEDULE_TOOLS
            + RAG_TOOLS
            + VECTOR_MEMORY_TOOLS
            + TIME_TOOLS
        )

        # Tool name to executor mapping
        self._quiz_tool_names = {"generate_test"}
        self._web_tool_names = {"web_search", "web_fetch"}
        self._schedule_tool_names = {"get_schedule", "add_schedule", "delete_schedule", "update_schedule"}
        self._rag_tool_names = {"search_documents"}
        self._vector_memory_tool_names = VECTOR_MEMORY_TOOL_NAMES
        self._time_tool_names = TIME_TOOL_NAMES

    async def process_message(
        self,
        user_message: str | dict[str, Any],
        history_messages: list[dict[str, str]],
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

        # 2. 使用向量检索获取相关记忆（语义搜索）
        relevant_memories = await self.memory_retriever.get_relevant_memories(
            user_message=message_text,
            max_long_term=5,
            max_space=5,
        )

        # 3. 格式化记忆用于 prompt 注入（标注本空间/共享来源）
        formatted_memories = format_memories_for_prompt(
            relevant_memories, current_space_id=self.space_id
        )

        # 4. Build system prompt with relevant memories and previous conversation context
        system_prompt = self.prompt_builder.build_system_prompt(
            space_id=self.space_id,
            space_name=self.space_name,
            relevant_memories=formatted_memories,
            previous_conversation_context=self.previous_conversation_context,
        )

        # Handle both string and dict formats for user message
        if isinstance(user_message, str):
            current_user_message = {"role": "user", "content": user_message}
        else:
            # Already in dict format (multimodal message)
            current_user_message = user_message

        # 2. Build messages array
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *history_messages,
            current_user_message,
        ]

        # 3. Initialize LLM context collector for feedback/debugging
        context_collector = LLMContextCollector(
            model=self.llm_client.model,
            initial_messages=copy.deepcopy(messages),
            tools=copy.deepcopy(self.available_tools),
            temperature=0.7,
            max_tokens=4096,
        )

        # 4. Multi-turn tool calling loop with streaming
        full_response = ""
        # Accumulate token usage across iterations
        total_prompt_tokens = 0
        total_completion_tokens = 0

        for iteration in range(MAX_TOOL_ITERATIONS):
            logger.debug(f"LLM iteration {iteration + 1}/{MAX_TOOL_ITERATIONS}")

            pending_tool_calls: list[ToolCall] = []
            iteration_content = ""
            finish_reason = None
            current_iteration = IterationData()

            try:
                # Use streaming method for real-time text output
                async for event in self.llm_client.stream_complete_with_tools(
                    messages=messages,
                    tools=self.available_tools,
                    temperature=0.7,
                ):
                    event_type = event.get("type")

                    # Immediately emit text content as it arrives
                    if event_type == "content":
                        content = event["content"]
                        iteration_content += content
                        full_response += content
                        current_iteration.content += content
                        yield {
                            "event": SSEEventType.TEXT_DELTA,
                            "data": {"content": content},
                        }

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

            except Exception as e:
                logger.error(f"LLM call failed: {e}", exc_info=True)
                yield {
                    "event": SSEEventType.ERROR,
                    "data": {"message": f"AI 服务暂时不可用: {str(e)}"},
                }
                return

            # Execute pending tool calls
            if pending_tool_calls:
                tool_results_for_context = []

                for tool_call in pending_tool_calls:
                    # Execute tool - dispatch to appropriate executor
                    if tool_call.name in self._quiz_tool_names:
                        tool_result = await self.quiz_tool_executor.execute(
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
                    else:
                        tool_result = await self.graph_tool_executor.execute(
                            tool_call.name,
                            tool_call.arguments,
                        )

                    # Store result for context
                    tool_results_for_context.append((tool_call, tool_result))

                    # Collect tool result for LLM context
                    if current_iteration.tool_results is None:
                        current_iteration.tool_results = []
                    current_iteration.tool_results.append({
                        "tool_call_id": tool_call.id,
                        "success": tool_result.success,
                        "data": tool_result.data,
                        "message": tool_result.message,
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
                        },
                    }

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
                for tool_call, tool_result in tool_results_for_context:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(
                                tool_result.to_dict(), ensure_ascii=False
                            ),
                        }
                    )

                # Continue loop to let LLM process tool results
                continue

            # No tool calls - check if we're done
            if not pending_tool_calls and finish_reason == "tool_calls":
                logger.warning(
                    "LLM indicated tool_calls but no tool_call_end events received. "
                    "This may indicate a streaming format issue."
                )
            if finish_reason == "stop" or not pending_tool_calls:
                # Append final iteration (no tool calls)
                if current_iteration.content:
                    context_collector.iterations.append(current_iteration)
                break

        # Finalize context collector
        context_collector.final_content = full_response
        context_collector.finish_reason = finish_reason or "stop"

        # Record API usage (fire-and-forget)
        if total_prompt_tokens > 0 or total_completion_tokens > 0:
            schedule_usage_recording(
                user_id=self.user_id,
                usage_type=UsageType.CHAT_LLM,
                model=self.llm_client.model,
                prompt_tokens=total_prompt_tokens,
                completion_tokens=total_completion_tokens,
                space_id=self.space_id,
                conversation_id=self.conversation_id,
            )

        # Emit done event with LLM context
        yield {
            "event": SSEEventType.DONE,
            "data": {
                "content": full_response,
                "llm_context": context_collector.to_dict(),
            },
        }

    # Note: 旧的 _load_long_term_memory 和 _load_space_memory 已被
    # MemoryRetriever.get_relevant_memories() 替代，使用语义检索而非全量加载
