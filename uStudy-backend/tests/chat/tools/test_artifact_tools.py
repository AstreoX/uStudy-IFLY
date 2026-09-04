"""Artifact tool guardrail tests."""

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import pytest


def _load_artifact_tools():
    """Load artifact_tools directly without importing the heavy chat.tools package."""
    if "agents" not in sys.modules:
        agents_pkg = types.ModuleType("agents")
        agents_pkg.__path__ = []  # type: ignore[attr-defined]
        sys.modules["agents"] = agents_pkg
    if "agents.llm" not in sys.modules:
        llm_pkg = types.ModuleType("agents.llm")
        llm_pkg.__path__ = []  # type: ignore[attr-defined]
        sys.modules["agents.llm"] = llm_pkg
    if "agents.llm.client" not in sys.modules:
        client_mod = types.ModuleType("agents.llm.client")
        client_mod.LLMClient = object  # type: ignore[attr-defined]
        sys.modules["agents.llm.client"] = client_mod
    if "config" not in sys.modules:
        config_mod = types.ModuleType("config")
        config_mod.get_settings = lambda: object()  # type: ignore[attr-defined]
        sys.modules["config"] = config_mod

    artifact_agent_path = (
        Path(__file__).parent.parent.parent.parent
        / "agents" / "artifact_agent.py"
    )
    agent_spec = importlib.util.spec_from_file_location(
        "agents.artifact_agent", artifact_agent_path
    )
    assert agent_spec is not None
    agent_mod = importlib.util.module_from_spec(agent_spec)
    assert agent_spec.loader is not None
    sys.modules["agents.artifact_agent"] = agent_mod
    agent_spec.loader.exec_module(agent_mod)  # type: ignore[union-attr]

    @dataclass
    class _ToolResult:
        success: bool
        data: object
        message: str
        image_base64: str | None = None

    sys.modules.setdefault("chat", types.ModuleType("chat"))
    tools_pkg = sys.modules.setdefault("chat.tools", types.ModuleType("chat.tools"))
    tools_pkg.__path__ = []  # type: ignore[attr-defined]
    base_mod = types.ModuleType("chat.tools.base")
    base_mod.ToolResult = _ToolResult  # type: ignore[attr-defined]
    sys.modules["chat.tools.base"] = base_mod

    schemas_mod = types.ModuleType("agents.schemas")
    schemas_mod.AgentTaskStatusEnum = object  # type: ignore[attr-defined]
    sys.modules["agents.schemas"] = schemas_mod

    db_database_mod = types.ModuleType("db.database")
    db_database_mod.get_scoped_session = lambda: None  # type: ignore[attr-defined]
    sys.modules.setdefault("db", types.ModuleType("db"))
    sys.modules["db.database"] = db_database_mod

    db_models_mod = types.ModuleType("db.models")
    for name in ("AgentTask", "AgentTaskStatus", "AgentTaskType", "Conversation", "Note"):
        setattr(db_models_mod, name, object)
    sys.modules["db.models"] = db_models_mod

    graph_service_mod = types.ModuleType("graph.service")
    graph_service_mod.GraphService = object  # type: ignore[attr-defined]
    sys.modules.setdefault("graph", types.ModuleType("graph"))
    sys.modules["graph.service"] = graph_service_mod

    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "chat" / "tools" / "artifact_tools.py"
    )
    spec = importlib.util.spec_from_file_location("chat.tools.artifact_tools", module_path)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_artifact_tools = _load_artifact_tools()
ARTIFACT_TOOLS = _artifact_tools.ARTIFACT_TOOLS
ArtifactToolExecutor = _artifact_tools.ArtifactToolExecutor


def test_create_artifact_tool_requires_description_in_prompt():
    tool = next(t for t in ARTIFACT_TOOLS if t["function"]["name"] == "create_artifact")

    assert "description" in tool["function"]["parameters"]["required"]
    assert "不要自行生成 HTML" in tool["function"]["description"]


def test_direct_html_argument_is_finalized_with_csp():
    html = "<!DOCTYPE html><html><head></head><body><h1>Demo</h1></body></html>"

    finalized = ArtifactToolExecutor._finalize_direct_html(html)

    assert "Content-Security-Policy" in finalized
    assert "connect-src 'none'" in finalized
    assert "<h1>Demo</h1>" in finalized


def test_direct_html_argument_rejects_non_html():
    with pytest.raises(ValueError, match="不是有效的交互演示 HTML"):
        ArtifactToolExecutor._finalize_direct_html("just text")
