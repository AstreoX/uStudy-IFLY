"""Tests for LLM context storage compaction."""

import importlib.util
import sys
from pathlib import Path


def _load_context_collector():
    module_path = Path(__file__).parent.parent.parent / "chat" / "context_collector.py"
    spec = importlib.util.spec_from_file_location("chat.context_collector_unit", module_path)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["chat.context_collector_unit"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_context_mod = _load_context_collector()
IterationData = _context_mod.IterationData
LLMContextCollector = _context_mod.LLMContextCollector


def test_context_collector_compacts_large_payloads():
    collector = LLMContextCollector(
        model="qwen3.6-plus",
        initial_messages=[
            {"role": "user", "content": "x" * 20000},
            {"role": "tool", "tool_call_id": "call-1", "content": "y" * 20000},
        ],
        tools=[{"function": {"name": "read_document"}}],
    )
    collector.iterations.append(
        IterationData(
            content="answer",
            tool_calls=[{"id": "call-1", "name": "read_document", "arguments": {}}],
            tool_results=[
                {
                    "tool_call_id": "call-1",
                    "success": True,
                    "data": {"base64": "z" * 20000, "content": "doc" * 5000},
                    "message": "ok",
                }
            ],
        )
    )

    result = collector.to_dict(max_chars=16000)

    assert result["response"]["context_truncated"] is True
    assert result["request"]["messages"][0]["content_chars"] == 20000
    assert result["response"]["iterations"][0]["tool_calls"][0]["id"] == "call-1"
    assert "base64" in result["response"]["iterations"][0]["tool_results"][0]["data"]
    assert "已省略" in result["response"]["iterations"][0]["tool_results"][0]["data"]["base64"]
