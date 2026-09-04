"""
Context Futures - Async background retrieval with tool-based access.

Holds asyncio.Tasks for memory and RAG retrieval that start immediately
when a user message arrives. Tools (get_context_memories, get_context_documents,
get_previous_context) await these futures, returning instantly if retrieval
has already completed.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from chat.tools.base import ToolResult
from memory.retriever import format_memories_for_prompt

logger = logging.getLogger(__name__)


@dataclass
class ContextFutures:
    """Holds background retrieval tasks. Context tools await these futures."""

    memory_task: asyncio.Task | None = None
    rag_task: asyncio.Task | None = None
    previous_context: str | None = None

    # Cached results after first await
    _memory_result: dict | None = field(default=None, repr=False)
    _memory_consumed: bool = False
    _rag_result: tuple[str | None, list[dict]] | None = field(default=None, repr=False)
    _rag_consumed: bool = False
    _previous_context_consumed: bool = False

    async def get_memories(self, current_space_id: UUID | None = None) -> ToolResult:
        """Await background memory retrieval. Returns instantly if already complete."""
        if self._memory_result is not None:
            formatted = format_memories_for_prompt(
                self._memory_result, current_space_id=current_space_id
            )
            self._memory_consumed = True
            return ToolResult(
                success=True,
                data=None,
                message=formatted or "没有找到相关记忆。",
            )

        if self.memory_task is None:
            return ToolResult(success=True, data=None, message="记忆检索未启动。")

        try:
            t0 = time.monotonic()
            self._memory_result = await self.memory_task
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.info("[ContextFutures] Memory await: %.0fms", elapsed_ms)

            formatted = format_memories_for_prompt(
                self._memory_result, current_space_id=current_space_id
            )
            self._memory_consumed = True
            return ToolResult(
                success=True,
                data=None,
                message=formatted or "没有找到相关记忆。",
            )
        except Exception as e:
            logger.warning("Memory retrieval failed: %s", e)
            self._memory_consumed = True
            return ToolResult(success=False, data=None, message=f"记忆检索失败: {e}")

    async def get_documents(self) -> ToolResult:
        """Await background RAG retrieval. Returns instantly if already complete."""
        if self._rag_result is not None:
            return self._build_rag_result(self._rag_result)

        if self.rag_task is None:
            return ToolResult(success=True, data=None, message="文档检索未启动。")

        try:
            t0 = time.monotonic()
            self._rag_result = await self.rag_task
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.info("[ContextFutures] RAG await: %.0fms", elapsed_ms)

            return self._build_rag_result(self._rag_result)
        except Exception as e:
            logger.warning("RAG retrieval failed: %s", e)
            self._rag_consumed = True
            return ToolResult(success=False, data=None, message=f"文档检索失败: {e}")

    def _build_rag_result(self, result: tuple[str | None, list[dict]]) -> ToolResult:
        rag_context, rag_citations = result
        self._rag_consumed = True
        if rag_context:
            return ToolResult(
                success=True,
                data={"context": rag_context, "citations": rag_citations},
                message=(
                    "以下是与当前话题相关的文档片段，引用时请在句末标注 [编号]：\n\n"
                    f"{rag_context}\n\n"
                    "引用标注规则：使用上述片段信息时，必须在句末标注来源编号如 [1]、[2]。"
                ),
            )
        return ToolResult(success=True, data=None, message="没有找到相关文档。")

    def get_previous_context(self) -> ToolResult:
        """Return previous conversation context (synchronous, already loaded)."""
        self._previous_context_consumed = True
        if self.previous_context:
            return ToolResult(
                success=True,
                data=None,
                message=(
                    "# 上一次对话参考（仅供背景了解）\n\n"
                    "以下是用户在此学习空间的上一次对话片段，供你了解用户近期学习状态和话题。\n"
                    "**重要**：这些内容仅作为背景参考，不要主动延续这些话题。"
                    "请等待用户在本次对话中明确表达他们的需求。\n\n"
                    "---\n\n"
                    f"{self.previous_context}\n\n"
                    "---\n\n"
                    "以上为历史参考。本次对话从用户的第一条消息开始。"
                ),
            )
        return ToolResult(success=True, data=None, message="没有上一次对话记录。")

    @property
    def all_consumed(self) -> bool:
        return (
            self._memory_consumed
            and self._rag_consumed
            and self._previous_context_consumed
        )

    def try_collect_unconsumed(
        self, current_space_id: UUID | None = None
    ) -> list[str]:
        """
        Collect results from completed-but-unconsumed tasks (for fallback injection).
        Only collects from tasks that are already done - never blocks.
        Returns list of formatted text sections.
        """
        parts: list[str] = []

        if not self._memory_consumed and self.memory_task and self.memory_task.done():
            try:
                result = self.memory_task.result()
                formatted = format_memories_for_prompt(
                    result, current_space_id=current_space_id
                )
                if formatted:
                    parts.append(formatted)
                self._memory_consumed = True
                self._memory_result = result
            except Exception:
                self._memory_consumed = True

        if not self._rag_consumed and self.rag_task and self.rag_task.done():
            try:
                rag_context, rag_citations = self.rag_task.result()
                if rag_context:
                    parts.append(
                        "# 相关文档内容\n\n"
                        f"{rag_context}\n\n"
                        "引用标注规则：使用上述片段信息时，必须在句末标注来源编号如 [1]、[2]。"
                    )
                self._rag_consumed = True
                self._rag_result = (rag_context, rag_citations)
            except Exception:
                self._rag_consumed = True

        if not self._previous_context_consumed and self.previous_context:
            parts.append(
                "# 上一次对话参考（仅供背景了解）\n\n"
                f"{self.previous_context}\n\n"
                "以上为历史参考。本次对话从用户的第一条消息开始。"
            )
            self._previous_context_consumed = True

        return parts

    def get_rag_citations(self) -> list[dict]:
        """Get RAG citations if available (for citation registry)."""
        if self._rag_result:
            _, citations = self._rag_result
            return citations
        if self.rag_task and self.rag_task.done():
            try:
                _, citations = self.rag_task.result()
                return citations
            except Exception:
                pass
        return []
