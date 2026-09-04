"""Hybrid mastery evaluation using the original LLM and paper-style dual-task model.

The LLM prompt/tool branch is unchanged. When a trained checkpoint is enabled, a
parallel dual-task branch predicts candidate relevance and five-class signed change;
the two results are fused once before graph writeback. Designed for background use.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from uuid import UUID

from agents.llm.client import LLMClient
from chat.tools.base import ToolResult
from chat.tools.graph_tools import GraphToolExecutor, build_knowledge_tree_text
from config import get_settings
from db.database import get_scoped_session
from graph.mastery_dual_task import (
    DualTaskMasteryClassifier,
    DualTaskPrediction,
    build_configured_dual_task_classifier,
    build_turn_node_input,
    fuse_mastery_decision,
    generate_candidate_nodes,
)
from graph.mastery_prompts import (
    build_mastery_evaluation_system_prompt,
    format_conversation_for_evaluation,
)
from graph.service import GraphService
from usage.metering import UsageContext
from usage.models import UsageType

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
    llm_mastery: int | None = None
    model_relevance: float | None = None
    model_change_class: int | None = None
    model_expected_change: float | None = None
    fused_relevance: float | None = None
    fused_change: float | None = None


@dataclass
class MasteryEvaluationResult:
    """Result of a mastery evaluation run."""

    updates: list[MasteryUpdateItem] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    dual_task_used: bool = False


class MasteryEvaluator:
    """Evaluates and updates knowledge graph mastery scores based on conversation."""

    def __init__(
        self,
        space_id: UUID,
        user_id: UUID | None = None,
        is_collaborative: bool = False,
        *,
        dual_task_classifier: DualTaskMasteryClassifier | None = None,
    ) -> None:
        self.space_id = space_id
        self.user_id = user_id
        self.is_collaborative = is_collaborative
        self.tool_executor = GraphToolExecutor(space_id, user_id=user_id, is_collaborative=is_collaborative)

        settings = get_settings()
        self.settings = settings
        self.dual_task_classifier = (
            dual_task_classifier
            if dual_task_classifier is not None
            else build_configured_dual_task_classifier(settings)
        )
        model_override = settings.mastery_evaluation_model or None
        self.llm_client = LLMClient(
            model_override=model_override,
            usage_context=UsageContext(
                user_id=user_id,
                usage_type=UsageType.AGENT_LLM,
                source_module="graph",
                source_operation="mastery_evaluation",
                billable=bool(user_id),
                space_id=space_id,
            ),
        )

    async def evaluate_and_update(
        self,
        conversation: list[dict],
        *,
        current_objective: str | None = None,
        current_path_node: str | None = None,
    ) -> MasteryEvaluationResult:
        """Evaluate conversation and update mastery scores.

        The original multi-turn LLM tool loop and the optional dual-task model run
        concurrently. Only the fused decisions are written to the graph.

        Args:
            conversation: List of message dicts from the conversation
            current_objective: Optional explicit objective used by SI candidate ranking
            current_path_node: Optional explicit active path node used by SI candidate ranking

        Returns:
            MasteryEvaluationResult with all updates
        """
        graph_data = await self._load_graph()
        if not graph_data["nodes"]:
            logger.info("Empty graph for space %s, skipping mastery evaluation", self.space_id)
            return MasteryEvaluationResult()

        mastery_map = {n["label"]: n.get("mastery") for n in graph_data["nodes"]}

        knowledge_tree_text = build_knowledge_tree_text(
            graph_data["nodes"], graph_data["edges"]
        )
        system_prompt = build_mastery_evaluation_system_prompt(knowledge_tree_text)
        user_content = format_conversation_for_evaluation(conversation)

        llm_messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        candidate_nodes = generate_candidate_nodes(
            conversation,
            graph_data["nodes"],
            graph_data["edges"],
            current_objective=current_objective,
            current_path_node=current_path_node,
            max_candidates=self.settings.mastery_dual_task_max_candidates,
            mastery_threshold=getattr(
                self.settings, "learning_path_mastery_threshold", 80
            ),
        )
        candidate_inputs = [
            build_turn_node_input(
                conversation,
                candidate,
                graph_data["nodes"],
                graph_data["edges"],
            )
            for candidate in candidate_nodes
        ]

        (llm_proposals, llm_failure_count), model_predictions = await asyncio.gather(
            self._collect_llm_proposals(llm_messages, mastery_map),
            self._predict_dual_task(candidate_inputs),
        )

        predictions_by_name = {prediction.node_name: prediction for prediction in model_predictions}
        nodes_by_name = {node["label"]: node for node in graph_data["nodes"]}
        ordered_node_names = [node["label"] for node in candidate_nodes]
        ordered_node_names.extend(
            node_name for node_name in llm_proposals if node_name not in ordered_node_names
        )

        updates: list[MasteryUpdateItem] = []
        success_count = 0
        failure_count = llm_failure_count
        for node_name in ordered_node_names:
            node = nodes_by_name.get(node_name)
            if node is None:
                continue
            old_mastery = node.get("mastery")
            model_prediction = predictions_by_name.get(node_name)
            decision = fuse_mastery_decision(
                node_name=node_name,
                current_mastery=old_mastery,
                llm_mastery=llm_proposals.get(node_name),
                model_prediction=model_prediction,
                relevance_threshold=self.settings.mastery_dual_task_relevance_threshold,
                model_relevance_weight=self.settings.mastery_fusion_relevance_weight,
                model_change_weight=self.settings.mastery_fusion_change_weight,
            )
            if not decision.selected or decision.new_mastery is None:
                continue

            comparison_mastery = old_mastery if old_mastery is not None and old_mastery >= 0 else 0
            if decision.new_mastery == comparison_mastery:
                continue

            tool_result = await self.tool_executor.execute(
                "update_mastery",
                {"node_name": node_name, "mastery": decision.new_mastery},
            )
            if not tool_result.success:
                failure_count += 1
                continue

            success_count += 1
            updates.append(
                MasteryUpdateItem(
                    node_name=node_name,
                    old_mastery=old_mastery,
                    new_mastery=decision.new_mastery,
                    change=decision.new_mastery - comparison_mastery,
                    llm_mastery=decision.llm_mastery,
                    model_relevance=decision.model_relevance,
                    model_change_class=(
                        model_prediction.predicted_change_class
                        if model_prediction is not None
                        else None
                    ),
                    model_expected_change=decision.model_expected_change,
                    fused_relevance=decision.fused_relevance,
                    fused_change=decision.fused_change,
                )
            )

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
            dual_task_used=bool(model_predictions),
        )

    async def _collect_llm_proposals(
        self,
        messages: list[dict],
        mastery_map: dict[str, int | None],
    ) -> tuple[dict[str, int], int]:
        """Run the original LLM branch without writing before hybrid fusion.

        The prompt, tool schema, temperature, iteration limit, and tool-result shape
        remain unchanged. Successful calls are staged as score proposals and are
        committed only after the dual-task branch has been fused.
        """

        staged_messages = list(messages)
        proposals: dict[str, int] = {}
        failure_count = 0
        for _ in range(MAX_EVAL_ITERATIONS):
            result = await self.llm_client.complete_with_tools(
                messages=staged_messages,
                tools=MASTERY_EVAL_TOOLS,
                temperature=0.3,
                max_tokens=1024,
            )
            if not result.tool_calls:
                break

            tool_results: list[tuple] = []
            for tool_call in result.tool_calls:
                tool_result = self._stage_llm_tool_call(tool_call.name, tool_call.arguments, mastery_map)
                tool_results.append((tool_call, tool_result))
                if tool_result.success:
                    node_name = str(tool_call.arguments.get("node_name", ""))
                    proposals[node_name] = int(tool_call.arguments["mastery"])
                else:
                    failure_count += 1

            staged_messages.append(
                {
                    "role": "assistant",
                    "content": result.content or "",
                    "tool_calls": [
                        {
                            "id": tool_call.id,
                            "type": "function",
                            "function": {
                                "name": tool_call.name,
                                "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                            },
                        }
                        for tool_call, _ in tool_results
                    ],
                }
            )
            for tool_call, tool_result in tool_results:
                staged_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result.to_dict(), ensure_ascii=False),
                    }
                )
            if result.finish_reason == "stop":
                break
        return proposals, failure_count

    @staticmethod
    def _stage_llm_tool_call(
        tool_name: str,
        arguments: dict,
        mastery_map: dict[str, int | None],
    ) -> ToolResult:
        """Validate an unchanged LLM tool call and return its normal result shape."""

        if tool_name != "update_mastery":
            return ToolResult(False, None, f"不支持的工具: {tool_name}")
        node_name = arguments.get("node_name", "")
        mastery = arguments.get("mastery")
        if not isinstance(node_name, str) or node_name not in mastery_map:
            return ToolResult(
                False,
                None,
                f"节点不存在: {node_name}。节点名称必须与知识图谱中已有节点完全匹配，请先调用 get_graph_overview 查看所有节点。",
            )
        if isinstance(mastery, bool) or not isinstance(mastery, int) or not 0 <= mastery <= 100:
            return ToolResult(False, None, "掌握分必须是 0-100 的整数")
        return ToolResult(
            True,
            {"node_name": node_name, "mastery": mastery},
            f"成功更新节点 {node_name} 的掌握分为 {mastery}",
        )

    async def _predict_dual_task(self, candidate_inputs) -> list[DualTaskPrediction]:
        """Predict with the trained checkpoint, falling back safely before training."""

        if self.dual_task_classifier is None or not candidate_inputs:
            return []
        try:
            predictions = await self.dual_task_classifier.predict(candidate_inputs)
        except Exception:
            logger.exception(
                "Dual-task mastery inference failed for space %s; using LLM-only fallback",
                self.space_id,
            )
            return []

        candidate_names = {item.node_name for item in candidate_inputs}
        valid_predictions: list[DualTaskPrediction] = []
        seen_names: set[str] = set()
        for prediction in predictions:
            if prediction.node_name not in candidate_names or prediction.node_name in seen_names:
                logger.warning("Ignoring unexpected dual-task prediction for node %s", prediction.node_name)
                continue
            seen_names.add(prediction.node_name)
            valid_predictions.append(prediction)
        return valid_predictions

    async def _load_graph(self) -> dict:
        """Load the knowledge graph for the space."""
        async with get_scoped_session() as db:
            graph_service = GraphService(db)
            return await graph_service.get_graph(self.space_id, user_id=self.user_id, is_collaborative=self.is_collaborative)
