"""LLM Context Collector for capturing complete API request/response data."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any


STRING_PREVIEW_CHARS = 4000
FINAL_CONTENT_PREVIEW_CHARS = 8000
REQUEST_MESSAGE_PREVIEW_CHARS = 1000
MAX_COMPACT_LIST_ITEMS = 20


@dataclass
class IterationData:
    """Single LLM call iteration data."""

    content: str = ""
    reasoning_content: str = ""
    tool_calls: list[dict[str, Any]] | None = None
    tool_results: list[dict[str, Any]] | None = None


@dataclass
class LLMContextCollector:
    """Collects complete LLM API interaction context for debugging and feedback.

    This collector captures:
    - The full request sent to the LLM (messages, tools, parameters)
    - The complete response including all tool call iterations
    - Tool execution results for each iteration

    Usage:
        collector = LLMContextCollector(
            model="openai/gpt-4o-mini",
            initial_messages=messages,
            tools=available_tools,
        )

        # During each iteration
        iteration = IterationData()
        iteration.content = "LLM response text"
        iteration.tool_calls = [{"id": "...", "name": "...", "arguments": {...}}]
        iteration.tool_results = [{"tool_call_id": "...", "success": True, ...}]
        collector.iterations.append(iteration)

        # After completion
        collector.final_content = full_response
        collector.finish_reason = "stop"

        # Convert to storable dict
        context_dict = collector.to_dict()
    """

    # Request part
    model: str = ""
    initial_messages: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096

    # Response part
    iterations: list[IterationData] = field(default_factory=list)
    final_content: str = ""
    finish_reason: str = ""

    def to_dict(self, max_chars: int | None = None) -> dict[str, Any]:
        """Convert to a storable dictionary format.

        Returns:
            Dict with 'request' and 'response' keys containing all context data.
        """
        data = {
            "request": {
                "model": self.model,
                "messages": copy.deepcopy(self.initial_messages),
                "tools": copy.deepcopy(self.tools),
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            },
            "response": {
                "iterations": [
                    {
                        "content": it.content,
                        "reasoning_content": it.reasoning_content,
                        "tool_calls": it.tool_calls,
                        "tool_results": it.tool_results,
                    }
                    for it in self.iterations
                ],
                "final_content": self.final_content,
                "total_iterations": len(self.iterations),
                "finish_reason": self.finish_reason,
            },
        }
        if not max_chars or _json_chars(data) <= max_chars:
            return data
        return self._to_compact_dict(max_chars, _json_chars(data))

    def _to_compact_dict(
        self,
        max_chars: int,
        original_chars: int,
    ) -> dict[str, Any]:
        compact = {
            "request": {
                "model": self.model,
                "messages": [_summarize_message(m) for m in self.initial_messages],
                "tools": [_tool_name(tool) for tool in self.tools],
                "tools_count": len(self.tools),
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            },
            "response": {
                "iterations": [
                    {
                        "content": _truncate_string(it.content, STRING_PREVIEW_CHARS),
                        "reasoning_content": _truncate_string(
                            it.reasoning_content,
                            STRING_PREVIEW_CHARS,
                        ),
                        "tool_calls": copy.deepcopy(it.tool_calls),
                        "tool_results": _compact_tool_results(it.tool_results),
                    }
                    for it in self.iterations
                ],
                "final_content": _truncate_string(
                    self.final_content,
                    FINAL_CONTENT_PREVIEW_CHARS,
                ),
                "total_iterations": len(self.iterations),
                "finish_reason": self.finish_reason,
                "context_truncated": True,
                "original_context_chars": original_chars,
                "max_context_chars": max_chars,
            },
        }
        if _json_chars(compact) <= max_chars:
            return compact

        compact["response"]["iterations"] = [
            {
                "content": _truncate_string(it.content, 1000),
                "reasoning_content": _truncate_string(it.reasoning_content, 1000),
                "tool_calls": copy.deepcopy(it.tool_calls),
                "tool_results": _minimal_tool_results(it.tool_results),
            }
            for it in self.iterations
        ]
        compact["response"]["final_content"] = _truncate_string(self.final_content, 2000)
        return compact


def _json_chars(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, default=str))


def _truncate_string(value: str | None, limit: int) -> str:
    if not value:
        return ""
    if len(value) <= limit:
        return value
    return f"{value[:limit]}\n[内容已压缩，原始长度 {len(value)} 字符]"


def _summarize_message(message: dict[str, Any]) -> dict[str, Any]:
    content = message.get("content")
    summary = {
        "role": message.get("role"),
        "content_chars": len(str(content)),
        "content_preview": _truncate_string(str(content), REQUEST_MESSAGE_PREVIEW_CHARS),
    }
    if message.get("tool_calls"):
        summary["tool_calls"] = copy.deepcopy(message.get("tool_calls"))
    if message.get("tool_call_id"):
        summary["tool_call_id"] = message.get("tool_call_id")
    return summary


def _tool_name(tool: dict[str, Any]) -> str:
    function = tool.get("function") if isinstance(tool, dict) else None
    if isinstance(function, dict):
        return str(function.get("name", ""))
    return str(tool)


def _compact_value(value: Any, *, string_limit: int = STRING_PREVIEW_CHARS, depth: int = 0) -> Any:
    if isinstance(value, str):
        if value.startswith("data:image"):
            return f"[图片数据已省略，原始长度 {len(value)} 字符]"
        return _truncate_string(value, string_limit)
    if isinstance(value, dict):
        compact: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if "base64" in key_text or key_text in {"image_bytes", "file_bytes"}:
                compact[key] = f"[二进制数据已省略，原始长度 {len(str(item))} 字符]"
                continue
            compact[key] = _compact_value(
                item,
                string_limit=max(500, string_limit // 2) if depth else string_limit,
                depth=depth + 1,
            )
        return compact
    if isinstance(value, list):
        items = [
            _compact_value(item, string_limit=max(500, string_limit // 2), depth=depth + 1)
            for item in value[:MAX_COMPACT_LIST_ITEMS]
        ]
        if len(value) > MAX_COMPACT_LIST_ITEMS:
            items.append({"compressed": True, "omitted_items": len(value) - MAX_COMPACT_LIST_ITEMS})
        return items
    return value


def _compact_tool_results(results: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if not results:
        return results
    return [
        {
            "tool_call_id": result.get("tool_call_id"),
            "success": result.get("success"),
            "data": _compact_value(result.get("data")),
            "message": _truncate_string(str(result.get("message") or ""), 1000),
        }
        for result in results
    ]


def _minimal_tool_results(results: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
    if not results:
        return results
    return [
        {
            "tool_call_id": result.get("tool_call_id"),
            "success": result.get("success"),
            "message": _truncate_string(str(result.get("message") or ""), 500),
            "data": {
                "compressed": True,
                "original_chars": _json_chars(result.get("data")),
                "message": "结果已压缩，仅保留工具调用元数据",
            },
        }
        for result in results
    ]
