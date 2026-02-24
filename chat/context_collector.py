"""LLM Context Collector for capturing complete API request/response data."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


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

    def to_dict(self) -> dict[str, Any]:
        """Convert to a storable dictionary format.

        Returns:
            Dict with 'request' and 'response' keys containing all context data.
        """
        return {
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
