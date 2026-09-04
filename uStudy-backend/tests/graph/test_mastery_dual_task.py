"""Tests for the paper-backed dual-task mastery assessment foundation."""

from types import SimpleNamespace

import pytest

from agents.llm.client import ToolCall
from chat.tools.base import ToolResult
from graph.mastery_dual_task import (
    DualTaskPrediction,
    TurnNodeInput,
    build_turn_node_input,
    extract_instruction_and_response,
    fuse_mastery_decision,
    generate_candidate_nodes,
    truncate_turn_node_text,
)
from graph.mastery_evaluator import MasteryEvaluator


NODES = [
    {"id": "root", "label": "数据结构", "mastery": 40},
    {"id": "array", "label": "数组", "mastery": 50},
    {"id": "list", "label": "链表", "mastery": 60},
    {"id": "stack", "label": "栈", "mastery": 30},
    {"id": "queue", "label": "队列", "mastery": 20},
]
EDGES = [
    {"from_node_id": "root", "to_node_id": "array", "type": "knowledge_tree"},
    {"from_node_id": "root", "to_node_id": "list", "type": "knowledge_tree"},
    {"from_node_id": "array", "to_node_id": "list", "type": "learning_path"},
    {"from_node_id": "list", "to_node_id": "stack", "type": "learning_path"},
    {"from_node_id": "array", "to_node_id": "queue", "type": "advanced"},
]
CONVERSATION = [
    {"role": "assistant", "content": "请比较数组与链表的访问方式。"},
    {"role": "user", "content": "数组支持按下标随机访问，链表通常要顺序查找。"},
    {"role": "assistant", "content": "这个比较是正确的。"},
]


def _prediction(
    node_name: str = "数组",
    relevance: float = 0.9,
    probabilities=(0.0, 0.0, 0.0, 0.0, 1.0),
) -> DualTaskPrediction:
    return DualTaskPrediction(
        node_id="array",
        node_name=node_name,
        relevance_probability=relevance,
        change_probabilities=probabilities,
    )


def test_extract_instruction_and_response_ignores_just_generated_answer():
    instruction, learner_response = extract_instruction_and_response(CONVERSATION)

    assert instruction == "请比较数组与链表的访问方式。"
    assert learner_response == "数组支持按下标随机访问，链表通常要顺序查找。"


def test_turn_node_serialization_uses_si_fixed_field_order():
    item = build_turn_node_input(CONVERSATION, NODES[1], NODES, EDGES)

    fields = [
        "[Instruction]",
        "[Learner Response]",
        "[Candidate Node]",
        "[Parent]",
        "[Children]",
        "[Incoming Relations]",
        "[Outgoing Relations]",
        "[Previous Path Node]",
        "[Next Path Node]",
    ]
    positions = [item.serialized_text.index(field) for field in fields]
    assert positions == sorted(positions)
    assert "[Parent] 数据结构" in item.serialized_text
    assert "[Outgoing Relations] 数组 -[advanced]-> 队列" in item.serialized_text
    assert "[Next Path Node] 链表" in item.serialized_text
    assert "mastery" not in item.serialized_text.casefold()


def test_candidate_generation_follows_si_priority_and_limit():
    candidates = generate_candidate_nodes(
        CONVERSATION,
        NODES,
        EDGES,
        current_objective="数组",
        current_path_node="链表",
        max_candidates=4,
    )

    assert [candidate["label"] for candidate in candidates] == [
        "数组",
        "链表",
        "数据结构",
        "队列",
    ]


class _CharacterTokenizer:
    def encode(self, text, add_special_tokens=True):
        tokens = [ord(character) for character in text]
        return ([1] + tokens + [2]) if add_special_tokens else tokens

    def decode(self, tokens, **kwargs):
        return "".join(chr(token) for token in tokens if token > 2)


def test_truncation_preserves_candidate_and_learner_response_before_other_fields():
    item = TurnNodeInput(
        node_id="array",
        node_name="数组",
        current_mastery=50,
        instructional_message="讲解" * 100,
        learner_response="完整学习者回答",
        local_topology="\n".join(
            (
                "[Parent] 数据结构",
                "[Children] [none]",
                "[Incoming Relations] 很长的入边关系",
                "[Outgoing Relations] 很长的出边关系",
                "[Previous Path Node] [none]",
                "[Next Path Node] 链表",
            )
        ),
        serialized_text="placeholder " * 100,
    )

    truncated = truncate_turn_node_text(item, _CharacterTokenizer(), max_length=230)

    assert "[Candidate Node] 数组" in truncated
    assert "[Learner Response] 完整学习者回答" in truncated
    assert truncated.index("[Instruction]") < truncated.index("[Learner Response]")
    assert truncated.index("[Learner Response]") < truncated.index("[Candidate Node]")
    assert "讲解" * 100 not in truncated


def test_fusion_without_checkpoint_preserves_original_llm_target():
    decision = fuse_mastery_decision(
        node_name="数组",
        current_mastery=50,
        llm_mastery=80,
        model_prediction=None,
    )

    assert decision.selected is True
    assert decision.new_mastery == 80
    assert decision.fused_change == 30


def test_fusion_combines_expected_five_class_delta_and_llm_delta():
    prediction = _prediction(relevance=0.9)

    decision = fuse_mastery_decision(
        node_name="数组",
        current_mastery=50,
        llm_mastery=65,
        model_prediction=prediction,
        model_relevance_weight=0.7,
        model_change_weight=0.5,
    )

    assert prediction.predicted_change_class == 2
    assert prediction.expected_change == 10
    assert decision.fused_relevance == pytest.approx(0.93)
    assert decision.fused_change == pytest.approx(12.5)
    assert decision.new_mastery == 62


def test_low_model_relevance_can_reject_an_llm_selected_node():
    decision = fuse_mastery_decision(
        node_name="数组",
        current_mastery=50,
        llm_mastery=60,
        model_prediction=_prediction(relevance=0.1),
        model_relevance_weight=0.7,
    )

    assert decision.fused_relevance == pytest.approx(0.37)
    assert decision.selected is False
    assert decision.new_mastery is None


class _MockLLMClient:
    def __init__(self, mastery: int):
        self.mastery = mastery
        self.calls: list[dict] = []

    async def complete_with_tools(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return SimpleNamespace(
                content="",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        name="update_mastery",
                        arguments={"node_name": "数组", "mastery": self.mastery},
                    )
                ],
                finish_reason="tool_calls",
            )
        return SimpleNamespace(content="完成", tool_calls=[], finish_reason="stop")


class _MockClassifier:
    async def predict(self, inputs):
        return [
            _prediction(node_name=item.node_name, relevance=0.9)
            if item.node_name == "数组"
            else DualTaskPrediction(
                node_id=item.node_id,
                node_name=item.node_name,
                relevance_probability=0.0,
                change_probabilities=(0.0, 0.0, 1.0, 0.0, 0.0),
            )
            for item in inputs
        ]


class _MockToolExecutor:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        return ToolResult(
            success=True,
            data={"node_name": arguments["node_name"], "mastery": arguments["mastery"]},
            message="ok",
        )


def _evaluator(classifier) -> MasteryEvaluator:
    evaluator = MasteryEvaluator.__new__(MasteryEvaluator)
    evaluator.space_id = "space-id"
    evaluator.user_id = "user-id"
    evaluator.is_collaborative = True
    evaluator.settings = SimpleNamespace(
        mastery_dual_task_max_candidates=10,
        mastery_dual_task_relevance_threshold=0.55,
        mastery_fusion_relevance_weight=0.7,
        mastery_fusion_change_weight=0.5,
    )
    evaluator.llm_client = _MockLLMClient(mastery=65)
    evaluator.dual_task_classifier = classifier
    evaluator.tool_executor = _MockToolExecutor()

    async def load_graph():
        return {"nodes": NODES, "edges": EDGES}

    evaluator._load_graph = load_graph
    return evaluator


@pytest.mark.asyncio
async def test_evaluator_runs_unchanged_llm_branch_then_commits_one_fused_update():
    evaluator = _evaluator(_MockClassifier())

    result = await evaluator.evaluate_and_update(CONVERSATION)

    assert evaluator.llm_client.calls[0]["temperature"] == 0.3
    assert evaluator.llm_client.calls[0]["max_tokens"] == 1024
    assert evaluator.llm_client.calls[0]["tools"][0]["function"]["name"] == "update_mastery"
    assert evaluator.tool_executor.calls == [
        ("update_mastery", {"node_name": "数组", "mastery": 62})
    ]
    assert result.success_count == 1
    assert result.dual_task_used is True
    assert result.updates[0].llm_mastery == 65
    assert result.updates[0].model_change_class == 2


@pytest.mark.asyncio
async def test_evaluator_without_checkpoint_keeps_llm_score_exactly():
    evaluator = _evaluator(None)

    result = await evaluator.evaluate_and_update(CONVERSATION)

    assert evaluator.tool_executor.calls == [
        ("update_mastery", {"node_name": "数组", "mastery": 65})
    ]
    assert result.dual_task_used is False


def test_dual_task_loss_uses_change_labels_only_for_relevant_pairs():
    torch = pytest.importorskip("torch")
    from graph.mastery_dual_task_torch import compute_dual_task_loss

    relevance_logits = torch.tensor([[2.0], [-2.0]], requires_grad=True)
    change_logits = torch.tensor(
        [[0.0, 0.0, 0.0, 0.0, 2.0], [10.0, 0.0, 0.0, 0.0, 0.0]],
        requires_grad=True,
    )
    relevance_labels = torch.tensor([1, 0])
    change_labels = torch.tensor([2, -2])

    total, node_loss, change_loss = compute_dual_task_loss(
        relevance_logits,
        change_logits,
        relevance_labels,
        change_labels,
        change_loss_weight=1.0,
    )

    assert total.item() == pytest.approx((node_loss + change_loss).item())
    total.backward()
    assert change_logits.grad[0].abs().sum() > 0
    assert change_logits.grad[1].abs().sum() == 0
