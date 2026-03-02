"""Learning path auto-expansion using multi-turn LLM tool calling.

When the majority of learning path nodes are mastered, this module
automatically extends the path to guide continued learning. Designed
to run as a background task chained after mastery evaluation.
"""

import json
import logging
from dataclasses import dataclass, field
from uuid import UUID

from agents.llm.client import OpenRouterClient
from chat.tools.graph_tools import (
    GraphToolExecutor,
    build_knowledge_tree_text,
    build_learning_path_chain,
)
from config import get_settings
from db.database import get_scoped_session
from graph.path_expansion_prompts import (
    build_path_expansion_system_prompt,
    format_learning_preferences,
    format_uncovered_nodes,
)
from graph.service import GraphService

logger = logging.getLogger(__name__)

MAX_EXPAND_ITERATIONS = 3

PATH_EXPAND_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "extend_learning_path",
            "description": "扩展当前学习路径。第一个节点必须是当前路径的末尾节点，后续节点为新增的学习内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_sequence": {
                        "type": "string",
                        "description": "节点名称序列，用逗号分隔。第一个必须是当前路径末尾节点，如 '链表,栈,队列'",
                    },
                },
                "required": ["node_sequence"],
            },
        },
    }
]


@dataclass
class PathExpansionResult:
    """Result of a learning path expansion attempt."""

    expanded: bool = False
    new_path_nodes: list[str] = field(default_factory=list)
    trigger_info: dict | None = None
    error: str | None = None


class LearningPathExpander:
    """Checks trigger conditions and expands learning paths via LLM."""

    def __init__(self, space_id: UUID, user_id: UUID) -> None:
        self.space_id = space_id
        self.user_id = user_id
        self.tool_executor = GraphToolExecutor(space_id)

        settings = get_settings()
        model_override = settings.learning_path_expand_model or None
        self.llm_client = OpenRouterClient(model_override=model_override)
        self.mastery_threshold = settings.learning_path_mastery_threshold
        self.ratio_threshold = settings.learning_path_ratio_threshold

    async def check_and_expand(self) -> PathExpansionResult:
        """Check trigger conditions and expand learning path if needed.

        Returns:
            PathExpansionResult with expansion details
        """
        try:
            graph_data = await self._load_graph()
            if not graph_data["nodes"]:
                return PathExpansionResult()

            trigger_info = self._should_expand(graph_data)
            if trigger_info is None:
                return PathExpansionResult()

            # Load user preferences
            preferences = await self._load_preferences()

            # Build context
            node_by_id = {n["id"]: n for n in graph_data["nodes"]}
            lp_edges = [
                e for e in graph_data["edges"] if e.get("type") == "learning_path"
            ]

            knowledge_tree_text = build_knowledge_tree_text(
                graph_data["nodes"], graph_data["edges"]
            )
            learning_path_text = build_learning_path_chain(
                lp_edges, node_by_id, with_index=True
            )
            uncovered_names = trigger_info["uncovered_names"]
            last_node_name = trigger_info["last_node"]

            preferences_text = format_learning_preferences(preferences)
            uncovered_text = format_uncovered_nodes(uncovered_names)

            system_prompt = build_path_expansion_system_prompt(
                knowledge_tree_text=knowledge_tree_text,
                learning_path_text=learning_path_text,
                last_path_node=last_node_name,
                uncovered_nodes_text=uncovered_text,
                preferences_text=preferences_text,
            )

            # Multi-turn LLM tool calling loop
            messages: list[dict] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "请分析当前学习进度并扩展学习路径。"},
            ]

            new_path_nodes: list[str] = []

            for iteration in range(MAX_EXPAND_ITERATIONS):
                result = await self.llm_client.complete_with_tools(
                    messages=messages,
                    tools=PATH_EXPAND_TOOLS,
                    temperature=0.3,
                    max_tokens=1024,
                )

                if not result.tool_calls:
                    break

                tool_results: list[tuple] = []
                for tc in result.tool_calls:
                    tool_result = await self.tool_executor.execute(
                        "extend_learning_path", tc.arguments
                    )
                    tool_results.append((tc, tool_result))

                    if tool_result.success:
                        # Extract new node names (skip the first which is the junction node)
                        seq = tc.arguments.get("node_sequence", "")
                        names = [n.strip() for n in seq.split(",")]
                        new_path_nodes.extend(names[1:])  # Exclude junction node

                # Build assistant message with tool calls
                assistant_msg: dict = {
                    "role": "assistant",
                    "content": result.content or "",
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
                        for tc, _ in tool_results
                    ],
                }
                messages.append(assistant_msg)

                for tc, tr in tool_results:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(tr.to_dict(), ensure_ascii=False),
                        }
                    )

                # If any tool succeeded, we're done
                if any(tr.success for _, tr in tool_results):
                    break

                if result.finish_reason == "stop":
                    break

            if not new_path_nodes:
                logger.info(
                    "Path expansion for space %s: LLM did not produce new nodes",
                    self.space_id,
                )
                return PathExpansionResult(trigger_info=trigger_info)

            # Persist expansion event
            await self._save_event(new_path_nodes, trigger_info)

            logger.info(
                "Learning path expanded for space %s: %d new nodes (%s)",
                self.space_id,
                len(new_path_nodes),
                ", ".join(new_path_nodes),
            )

            return PathExpansionResult(
                expanded=True,
                new_path_nodes=new_path_nodes,
                trigger_info=trigger_info,
            )

        except Exception as e:
            logger.error(
                "Path expansion failed for space %s: %s",
                self.space_id,
                e,
                exc_info=True,
            )
            return PathExpansionResult(error=str(e))

    def _should_expand(self, graph_data: dict) -> dict | None:
        """Check whether expansion should be triggered.

        Returns:
            trigger_info dict if should expand, None otherwise
        """
        edges = graph_data["edges"]
        nodes = graph_data["nodes"]

        lp_edges = [e for e in edges if e.get("type") == "learning_path"]
        if not lp_edges:
            return None

        # Collect path node IDs
        path_node_ids: set[str] = set()
        from_ids: set[str] = set()
        to_ids: set[str] = set()
        for e in lp_edges:
            fid = e["from_node_id"]
            tid = e["to_node_id"]
            path_node_ids.add(fid)
            path_node_ids.add(tid)
            from_ids.add(fid)
            to_ids.add(tid)

        total_path_nodes = len(path_node_ids)
        if total_path_nodes == 0:
            return None

        # Count high-mastery nodes
        node_by_id = {n["id"]: n for n in nodes}
        high_mastery_count = 0
        for nid in path_node_ids:
            node = node_by_id.get(nid)
            if node and (node.get("mastery") or 0) > self.mastery_threshold:
                high_mastery_count += 1

        ratio = high_mastery_count / total_path_nodes
        if ratio < self.ratio_threshold:
            return None

        # Check uncovered nodes
        all_node_ids = {n["id"] for n in nodes}
        uncovered_ids = all_node_ids - path_node_ids
        if not uncovered_ids:
            return None

        uncovered_names = [
            node_by_id[nid]["label"]
            for nid in uncovered_ids
            if nid in node_by_id
        ]

        # Find terminal nodes (no outgoing edge in the path)
        terminal_ids = path_node_ids - from_ids
        if not terminal_ids:
            # All nodes have successors — cycle or error; pick last to_id
            terminal_ids = to_ids - from_ids
            if not terminal_ids:
                return None

        # Pick one terminal node (there should usually be exactly one)
        last_node_id = next(iter(terminal_ids))
        last_node = node_by_id.get(last_node_id)
        last_node_name = last_node["label"] if last_node else "unknown"

        return {
            "total_path_nodes": total_path_nodes,
            "high_mastery_count": high_mastery_count,
            "ratio": round(ratio, 2),
            "uncovered_count": len(uncovered_ids),
            "uncovered_names": uncovered_names,
            "last_node": last_node_name,
        }

    async def _load_graph(self) -> dict:
        """Load the knowledge graph for the space."""
        async with get_scoped_session() as db:
            graph_service = GraphService(db)
            return await graph_service.get_graph(self.space_id)

    async def _load_preferences(self) -> dict | None:
        """Load user learning preferences for the space."""
        from db.models import Space
        from sqlalchemy import select

        async with get_scoped_session() as db:
            result = await db.execute(
                select(Space.learning_preferences).where(Space.id == self.space_id)
            )
            row = result.scalar_one_or_none()
            return row if isinstance(row, dict) else None

    async def _save_event(
        self, new_node_names: list[str], trigger_info: dict
    ) -> None:
        """Persist the expansion event to the database."""
        from db.models import LearningPathEvent

        async with get_scoped_session() as db:
            event = LearningPathEvent(
                space_id=self.space_id,
                user_id=self.user_id,
                new_node_names=new_node_names,
                trigger_info=trigger_info,
            )
            db.add(event)
            await db.commit()
