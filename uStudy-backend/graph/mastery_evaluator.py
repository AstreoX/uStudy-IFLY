"""Mastery evaluation using multi-turn LLM tool calling.

Evaluates student mastery based on conversation content and updates
knowledge graph nodes accordingly. Designed to run as a background task.
"""

import json
import logging
from dataclasses import dataclass, field
from uuid import UUID

from agents.llm.client import OpenRouterClient
from chat.tools.graph_tools import GraphToolExecutor, build_knowledge_tree_text
from config import get_settings
from db.database import get_scoped_session
from graph.mastery_prompts import (
    build_mastery_evaluation_system_prompt,
    format_conversation_for_evaluation,
)
from graph.service import GraphService

logger = logging.getLogger(__name__)

MAX_EVAL_ITERATIONS = 3

MASTERY_EVAL_TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "update_mastery",
            "description": "更新指定知识点节点的掌握分",
            "parameters": {
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "知识点节点名称（必须与知识图谱中的名称完全匹配）",
                    },
                    "mastery": {
                        "type": "integer",
                        "description": "新的掌握分（0-100）",
                        "minimum": 0,
                        "maximum": 100,
                    },
                },
                "required": ["node_name", "mastery"],
            },
        },
    }
]


@dataclass
class MasteryUpdateItem:
    """A single mastery update result."""

    node_name: str
    old_mastery: int | None
    new_mastery: int
    change: int


@dataclass
class MasteryEvaluationResult:
    """Result of a mastery evaluation run."""

    updates: list[MasteryUpdateItem] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0


class MasteryEvaluator:
    """Evaluates and updates knowledge graph mastery scores based on conversation."""

    def __init__(self, space_id: UUID, user_id: UUID | None = None, is_collaborative: bool = False) -> None:
        self.space_id = space_id
        self.user_id = user_id
        self.is_collaborative = is_collaborative
        self.tool_executor = GraphToolExecutor(space_id, user_id=user_id, is_collaborative=is_collaborative)

        settings = get_settings()
        model_override = settings.mastery_evaluation_model or None
        self.llm_client = OpenRouterClient(model_override=model_override)

    async def evaluate_and_update(
        self, conversation: list[dict]
    ) -> MasteryEvaluationResult:
        """Evaluate conversation and update mastery scores.

        Uses a multi-turn tool calling loop so the LLM can see tool results
        and retry on failure (e.g. wrong node name).

        Args:
            conversation: List of message dicts from the conversation

        Returns:
            MasteryEvaluationResult with all updates
        """
        graph_data = await self._load_graph()
        if not graph_data["nodes"]:
            logger.info("Empty graph for space %s, skipping mastery evaluation", self.space_id)
            return MasteryEvaluationResult()

        mastery_map = {
            n["label"]: n.get("mastery") for n in graph_data["nodes"]
        }

        knowledge_tree_text = build_knowledge_tree_text(
            graph_data["nodes"], graph_data["edges"]
        )
        system_prompt = build_mastery_evaluation_system_prompt(knowledge_tree_text)
        user_content = format_conversation_for_evaluation(conversation)

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        updates: list[MasteryUpdateItem] = []
        success_count = 0
        failure_count = 0

        for iteration in range(MAX_EVAL_ITERATIONS):
            result = await self.llm_client.complete_with_tools(
                messages=messages,
                tools=MASTERY_EVAL_TOOLS,
                temperature=0.3,
                max_tokens=1024,
            )

            if not result.tool_calls:
                break

            tool_results: list[tuple] = []
            for tc in result.tool_calls:
                tool_result = await self.tool_executor.execute(
                    "update_mastery", tc.arguments
                )
                tool_results.append((tc, tool_result))

                if tool_result.success:
                    success_count += 1
                    node_name = tc.arguments.get("node_name", "")
                    new_mastery = tc.arguments.get("mastery", 0)
                    old_mastery = mastery_map.get(node_name)
                    change = new_mastery - (old_mastery if old_mastery is not None else 0)
                    updates.append(
                        MasteryUpdateItem(
                            node_name=node_name,
                            old_mastery=old_mastery,
                            new_mastery=new_mastery,
                            change=change,
                        )
                    )
                else:
                    failure_count += 1

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

            if result.finish_reason == "stop":
                break

        logger.info(
            "Mastery evaluation for space %s: %d updates, %d failures",
            self.space_id,
            success_count,
            failure_count,
        )

        return MasteryEvaluationResult(
            updates=updates,
            success_count=success_count,
            failure_count=failure_count,
        )

    async def _load_graph(self) -> dict:
        """Load the knowledge graph for the space."""
        async with get_scoped_session() as db:
            graph_service = GraphService(db)
            return await graph_service.get_graph(self.space_id, user_id=self.user_id, is_collaborative=self.is_collaborative)
