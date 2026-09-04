"""Dual-task mastery assessment primitives and hybrid fusion.

The paper-backed branch contains two predictions for every turn-node pair:

1. binary candidate-node relevance; and
2. five-class signed mastery change ``{-2, -1, 0, +1, +2}``.

The local PyTorch implementation is loaded lazily so deployments that have not yet
trained a checkpoint continue to use the existing LLM-only evaluator.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol, Sequence

logger = logging.getLogger(__name__)

CHANGE_CLASSES: tuple[int, ...] = (-2, -1, 0, 1, 2)
CHANGE_DELTAS: tuple[int, ...] = (-10, -5, 0, 5, 10)


@dataclass(frozen=True)
class TurnNodeInput:
    """Serialized assessment input for one dialogue turn and candidate node."""

    node_id: str
    node_name: str
    current_mastery: int | None
    serialized_text: str
    instructional_message: str = ""
    learner_response: str = ""
    local_topology: str = ""


@dataclass(frozen=True)
class DualTaskPrediction:
    """Dual-task probabilities for one turn-node pair."""

    node_id: str
    node_name: str
    relevance_probability: float
    change_probabilities: tuple[float, float, float, float, float]

    def __post_init__(self) -> None:
        if not 0.0 <= self.relevance_probability <= 1.0:
            raise ValueError("relevance_probability must be between 0 and 1")
        if len(self.change_probabilities) != len(CHANGE_CLASSES):
            raise ValueError("change_probabilities must contain exactly five values")
        if any(probability < 0.0 or probability > 1.0 for probability in self.change_probabilities):
            raise ValueError("change probabilities must be between 0 and 1")
        if abs(sum(self.change_probabilities) - 1.0) > 1e-4:
            raise ValueError("change probabilities must sum to 1")

    @property
    def expected_change(self) -> float:
        """Expected mastery-score delta under the paper's class mapping."""

        return sum(
            probability * delta
            for probability, delta in zip(self.change_probabilities, CHANGE_DELTAS)
        )

    @property
    def predicted_change_class(self) -> int:
        """Return the maximum-probability ordinal class."""

        index = max(range(len(self.change_probabilities)), key=self.change_probabilities.__getitem__)
        return CHANGE_CLASSES[index]


class DualTaskMasteryClassifier(Protocol):
    """Inference contract implemented by trained dual-task checkpoints."""

    async def predict(self, inputs: Sequence[TurnNodeInput]) -> list[DualTaskPrediction]:
        """Predict relevance and five-class mastery change for every input."""


@dataclass(frozen=True)
class HybridMasteryDecision:
    """Auditable result of combining the dual-task and LLM branches."""

    node_name: str
    selected: bool
    current_mastery: int | None
    llm_mastery: int | None
    llm_change: float | None
    model_relevance: float | None
    model_expected_change: float | None
    fused_relevance: float
    fused_change: float
    new_mastery: int | None


def _message_text(message: dict) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            str(part.get("text", "")).strip()
            for part in content
            if isinstance(part, dict) and part.get("type") == "text" and part.get("text")
        ).strip()
    return str(content).strip() if content is not None else ""


def extract_instruction_and_response(conversation: Sequence[dict]) -> tuple[str, str]:
    """Extract the latest learner response and the preceding instructional message.

    Assessment currently runs after an assistant response is persisted. The learner
    response is therefore the latest user message, and the instructional message is
    the closest assistant message preceding it. This preserves the paper's ``a_t,
    r_t`` ordering instead of treating the just-generated assistant answer as learner
    evidence.
    """

    latest_user_index: int | None = None
    learner_response = ""
    for index in range(len(conversation) - 1, -1, -1):
        message = conversation[index]
        if message.get("role") == "user" and _message_text(message):
            latest_user_index = index
            learner_response = _message_text(message)
            break

    if latest_user_index is None:
        return "", ""

    instructional_message = ""
    for index in range(latest_user_index - 1, -1, -1):
        message = conversation[index]
        if message.get("role") == "assistant" and _message_text(message):
            instructional_message = _message_text(message)
            break

    return instructional_message, learner_response


def build_local_topology(
    candidate_node_id: str,
    nodes: Sequence[dict],
    edges: Sequence[dict],
) -> str:
    """Serialize candidate-centered one-hop graph context.

    The fields mirror the main manuscript: parents, children, incoming/outgoing
    non-tree links, and adjacent nodes on the current learning path.
    """

    labels = {str(node.get("id")): str(node.get("label", "")) for node in nodes}
    groups: dict[str, list[str]] = {
        "parent_nodes": [],
        "child_nodes": [],
        "incoming_non_tree_edges": [],
        "outgoing_non_tree_edges": [],
        "learning_path_neighbors": [],
    }

    for edge in edges:
        source_id = str(edge.get("from_node_id", ""))
        target_id = str(edge.get("to_node_id", ""))
        edge_type = str(edge.get("type", ""))
        source_label = labels.get(source_id, source_id)
        target_label = labels.get(target_id, target_id)

        if edge_type == "knowledge_tree":
            if target_id == candidate_node_id:
                groups["parent_nodes"].append(source_label)
            if source_id == candidate_node_id:
                groups["child_nodes"].append(target_label)
        elif edge_type == "learning_path":
            if target_id == candidate_node_id:
                groups["learning_path_neighbors"].append(source_label)
            if source_id == candidate_node_id:
                groups["learning_path_neighbors"].append(target_label)
        else:
            if target_id == candidate_node_id:
                groups["incoming_non_tree_edges"].append(
                    f"{source_label} -[{edge_type}]-> {labels.get(candidate_node_id, candidate_node_id)}"
                )
            if source_id == candidate_node_id:
                groups["outgoing_non_tree_edges"].append(
                    f"{labels.get(candidate_node_id, candidate_node_id)} -[{edge_type}]-> {target_label}"
                )

    field_order = (
        ("Parent", "parent_nodes"),
        ("Children", "child_nodes"),
        ("Incoming Relations", "incoming_non_tree_edges"),
        ("Outgoing Relations", "outgoing_non_tree_edges"),
    )
    lines: list[str] = []
    for output_name, group_name in field_order:
        unique_values = sorted(set(value for value in groups[group_name] if value))
        lines.append(f"[{output_name}] {', '.join(unique_values) if unique_values else '[none]'}")

    previous_path_nodes: list[str] = []
    next_path_nodes: list[str] = []
    for edge in edges:
        if str(edge.get("type", "")) != "learning_path":
            continue
        source_id = str(edge.get("from_node_id", ""))
        target_id = str(edge.get("to_node_id", ""))
        if target_id == candidate_node_id:
            previous_path_nodes.append(labels.get(source_id, source_id))
        if source_id == candidate_node_id:
            next_path_nodes.append(labels.get(target_id, target_id))
    lines.append(
        f"[Previous Path Node] {', '.join(sorted(set(previous_path_nodes))) if previous_path_nodes else '[none]'}"
    )
    lines.append(
        f"[Next Path Node] {', '.join(sorted(set(next_path_nodes))) if next_path_nodes else '[none]'}"
    )
    return "\n".join(lines)


def build_turn_node_input(
    conversation: Sequence[dict],
    candidate: dict,
    nodes: Sequence[dict],
    edges: Sequence[dict],
) -> TurnNodeInput:
    """Build one paper-style turn-node input in a stable field order."""

    instruction, learner_response = extract_instruction_and_response(conversation)
    node_id = str(candidate.get("id", ""))
    node_name = str(candidate.get("label", ""))
    local_topology = build_local_topology(node_id, nodes, edges)
    serialized = "\n".join(
        (
            f"[Instruction] {instruction or '[none]'}",
            f"[Learner Response] {learner_response or '[none]'}",
            f"[Candidate Node] {node_name}",
            local_topology,
        )
    )
    return TurnNodeInput(
        node_id=node_id,
        node_name=node_name,
        current_mastery=candidate.get("mastery"),
        serialized_text=serialized,
        instructional_message=instruction,
        learner_response=learner_response,
        local_topology=local_topology,
    )


def truncate_turn_node_text(item: TurnNodeInput, tokenizer, max_length: int) -> str:
    """Apply the SI S1.1 token-preservation order while keeping fixed field order."""

    full_token_ids = tokenizer.encode(item.serialized_text, add_special_tokens=True)
    if len(full_token_ids) <= max_length:
        return item.serialized_text
    if not item.local_topology:
        return item.serialized_text

    topology_values: dict[str, str] = {}
    for line in item.local_topology.splitlines():
        if not line.startswith("[") or "]" not in line:
            continue
        tag, value = line.split("]", 1)
        topology_values[tag[1:]] = value.strip()

    fields = {
        "Instruction": item.instructional_message or "[none]",
        "Learner Response": item.learner_response or "[none]",
        "Candidate Node": item.node_name,
        "Parent": topology_values.get("Parent", "[none]"),
        "Children": topology_values.get("Children", "[none]"),
        "Incoming Relations": topology_values.get("Incoming Relations", "[none]"),
        "Outgoing Relations": topology_values.get("Outgoing Relations", "[none]"),
        "Previous Path Node": topology_values.get("Previous Path Node", "[none]"),
        "Next Path Node": topology_values.get("Next Path Node", "[none]"),
    }
    fixed_order = (
        "Instruction",
        "Learner Response",
        "Candidate Node",
        "Parent",
        "Children",
        "Incoming Relations",
        "Outgoing Relations",
        "Previous Path Node",
        "Next Path Node",
    )
    preservation_order = (
        "Candidate Node",
        "Learner Response",
        "Instruction",
        "Parent",
        "Children",
        "Previous Path Node",
        "Next Path Node",
        "Incoming Relations",
        "Outgoing Relations",
    )

    empty_template = "\n".join(f"[{name}]" for name in fixed_order)
    overhead = len(tokenizer.encode(empty_template, add_special_tokens=True))
    remaining = max(0, max_length - overhead)
    retained_tokens: dict[str, list[int]] = {name: [] for name in fixed_order}
    for name in preservation_order:
        token_ids = tokenizer.encode(fields[name], add_special_tokens=False)
        retained_tokens[name] = token_ids[:remaining]
        remaining -= len(retained_tokens[name])
        if remaining <= 0:
            break

    truncated = "\n".join(
        f"[{name}] "
        + tokenizer.decode(
            retained_tokens[name],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )
        for name in fixed_order
    )
    return truncated


def generate_candidate_nodes(
    conversation: Sequence[dict],
    nodes: Sequence[dict],
    edges: Sequence[dict],
    *,
    current_objective: str | None = None,
    current_path_node: str | None = None,
    max_candidates: int = 10,
    mastery_threshold: int = 80,
) -> list[dict]:
    """Construct ``C_t`` using the fixed SI S1.1 sources and priority order.

    Priority is: current objective, current path node, learner-response text match,
    parent/child, cross-branch neighbour, and other adjacent path node. Ties are
    ordered by shortest undirected graph distance from the current objective.
    """

    if max_candidates < 1:
        raise ValueError("max_candidates must be at least 1")
    if not 0 <= mastery_threshold <= 100:
        raise ValueError("mastery_threshold must be between 0 and 100")

    node_by_id = {str(node.get("id")): node for node in nodes}
    id_by_name = {str(node.get("label", "")): str(node.get("id")) for node in nodes}
    _, learner_response = extract_instruction_and_response(conversation)
    response_text = learner_response.casefold()

    path_edges = [edge for edge in edges if str(edge.get("type", "")) == "learning_path"]
    path_source_ids = {str(edge.get("from_node_id", "")) for edge in path_edges}
    path_target_ids = {str(edge.get("to_node_id", "")) for edge in path_edges}
    current_path_id = id_by_name.get(current_path_node or "")
    if current_path_id is None and path_edges:
        next_by_id = {
            str(edge.get("from_node_id", "")): str(edge.get("to_node_id", ""))
            for edge in path_edges
        }
        path_starts = sorted(
            path_source_ids - path_target_ids,
            key=lambda node_id: str(node_by_id.get(node_id, {}).get("label", "")),
        )
        path_sequence: list[str] = []
        if path_starts:
            cursor = path_starts[0]
            visited: set[str] = set()
            while cursor and cursor not in visited:
                visited.add(cursor)
                path_sequence.append(cursor)
                cursor = next_by_id.get(cursor, "")
        for node_id in path_sequence:
            mastery = node_by_id.get(node_id, {}).get("mastery")
            if mastery is None or mastery < 0 or mastery < mastery_threshold:
                current_path_id = node_id
                break
        if current_path_id is None and path_sequence:
            current_path_id = path_sequence[-1]

    objective_id = id_by_name.get(current_objective or "")
    if objective_id is None:
        objective_id = current_path_id

    priorities: dict[str, int] = {}

    def add_candidate(node_id: str | None, priority: int) -> None:
        if node_id and node_id in node_by_id:
            priorities[node_id] = min(priorities.get(node_id, priority), priority)

    add_candidate(objective_id, 0)
    add_candidate(current_path_id, 1)

    text_matched_ids: set[str] = set()
    for node_id, node in node_by_id.items():
        label = str(node.get("label", "")).strip()
        if label and label.casefold() in response_text:
            text_matched_ids.add(node_id)
            add_candidate(node_id, 2)

    local_seeds = {node_id for node_id in (objective_id, current_path_id) if node_id}
    if not local_seeds:
        local_seeds = set(text_matched_ids)

    for edge in edges:
        source_id = str(edge.get("from_node_id", ""))
        target_id = str(edge.get("to_node_id", ""))
        edge_type = str(edge.get("type", ""))
        if edge_type == "knowledge_tree":
            if source_id in local_seeds:
                add_candidate(target_id, 3)
            if target_id in local_seeds:
                add_candidate(source_id, 3)
        elif edge_type != "learning_path":
            if source_id in local_seeds:
                add_candidate(target_id, 4)
            if target_id in local_seeds:
                add_candidate(source_id, 4)

    for edge in path_edges:
        source_id = str(edge.get("from_node_id", ""))
        target_id = str(edge.get("to_node_id", ""))
        if source_id == current_path_id:
            add_candidate(target_id, 5)
        if target_id == current_path_id:
            add_candidate(source_id, 5)

    if not priorities:
        priorities = {node_id: 6 for node_id in node_by_id}

    adjacency: dict[str, set[str]] = {node_id: set() for node_id in node_by_id}
    for edge in edges:
        source_id = str(edge.get("from_node_id", ""))
        target_id = str(edge.get("to_node_id", ""))
        if source_id in adjacency and target_id in adjacency:
            adjacency[source_id].add(target_id)
            adjacency[target_id].add(source_id)

    distances: dict[str, int] = {}
    if objective_id in adjacency:
        distances[objective_id] = 0
        queue = [objective_id]
        for node_id in queue:
            for neighbor_id in sorted(adjacency[node_id]):
                if neighbor_id not in distances:
                    distances[neighbor_id] = distances[node_id] + 1
                    queue.append(neighbor_id)

    ranked_ids = sorted(
        priorities,
        key=lambda node_id: (
            priorities[node_id],
            distances.get(node_id, len(node_by_id) + 1),
            str(node_by_id[node_id].get("label", "")),
        ),
    )
    return [node_by_id[node_id] for node_id in ranked_ids[:max_candidates]]


def fuse_mastery_decision(
    *,
    node_name: str,
    current_mastery: int | None,
    llm_mastery: int | None,
    model_prediction: DualTaskPrediction | None,
    relevance_threshold: float = 0.55,
    model_relevance_weight: float = 0.7,
    model_change_weight: float = 0.5,
    max_llm_delta: int = 15,
) -> HybridMasteryDecision:
    """Fuse dual-task probabilities with the existing LLM branch.

    With both branches available, the formulas are::

        p_rel^H = beta * p_rel^BERT + (1-beta) * I(LLM selected node)
        delta_BERT = sum_k P(y_change=k) * {-10,-5,0,+5,+10}_k
        delta^H = alpha * delta_BERT + (1-alpha) * clip(delta_LLM, -15, 15)
        m_(t+1) = clip_[0,100](m_t + round(delta^H))

    If the checkpoint is absent or inference fails, ``model_prediction`` is ``None``
    and the original LLM target is returned unchanged.
    """

    for name, value in (
        ("relevance_threshold", relevance_threshold),
        ("model_relevance_weight", model_relevance_weight),
        ("model_change_weight", model_change_weight),
    ):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1")
    if max_llm_delta < 1:
        raise ValueError("max_llm_delta must be at least 1")

    normalized_current = None if current_mastery is None or current_mastery < 0 else max(0, min(100, int(current_mastery)))
    normalized_llm = None if llm_mastery is None else max(0, min(100, int(llm_mastery)))
    base_mastery = normalized_current if normalized_current is not None else 0
    llm_selected = normalized_llm is not None
    raw_llm_change = float(normalized_llm - base_mastery) if llm_selected else None

    if model_prediction is None:
        return HybridMasteryDecision(
            node_name=node_name,
            selected=llm_selected,
            current_mastery=current_mastery,
            llm_mastery=normalized_llm,
            llm_change=raw_llm_change,
            model_relevance=None,
            model_expected_change=None,
            fused_relevance=1.0 if llm_selected else 0.0,
            fused_change=raw_llm_change or 0.0,
            new_mastery=normalized_llm,
        )

    model_relevance = max(0.0, min(1.0, float(model_prediction.relevance_probability)))
    fused_relevance = (
        model_relevance_weight * model_relevance
        + (1.0 - model_relevance_weight) * float(llm_selected)
    )
    selected = fused_relevance >= relevance_threshold
    model_change = model_prediction.expected_change

    if not selected:
        fused_change = 0.0
        new_mastery = None
    else:
        if raw_llm_change is None:
            fused_change = model_change
        else:
            bounded_llm_change = max(-max_llm_delta, min(max_llm_delta, raw_llm_change))
            fused_change = (
                model_change_weight * model_change
                + (1.0 - model_change_weight) * bounded_llm_change
            )
        new_mastery = max(0, min(100, base_mastery + round(fused_change)))

    return HybridMasteryDecision(
        node_name=node_name,
        selected=selected,
        current_mastery=current_mastery,
        llm_mastery=normalized_llm,
        llm_change=raw_llm_change,
        model_relevance=model_relevance,
        model_expected_change=model_change,
        fused_relevance=fused_relevance,
        fused_change=fused_change,
        new_mastery=new_mastery,
    )


class LocalDualTaskMasteryClassifier:
    """Lazy local inference adapter for a trained dual-task checkpoint."""

    def __init__(
        self,
        checkpoint_path: str | Path,
        *,
        max_length: int = 512,
        batch_size: int = 16,
        device: str = "cpu",
    ) -> None:
        self.checkpoint_path = Path(checkpoint_path)
        if not self.checkpoint_path.is_dir():
            raise FileNotFoundError(f"Dual-task checkpoint not found: {self.checkpoint_path}")
        if max_length < 8:
            raise ValueError("max_length must be at least 8")
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self.max_length = max_length
        self.batch_size = batch_size
        self.device = device
        self._model = None
        self._tokenizer = None
        self._load_lock = threading.Lock()

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            from graph.mastery_dual_task_torch import load_dual_task_checkpoint

            self._model, self._tokenizer = load_dual_task_checkpoint(
                self.checkpoint_path,
                device=self.device,
            )

    def _predict_sync(self, inputs: Sequence[TurnNodeInput]) -> list[DualTaskPrediction]:
        self._ensure_loaded()
        if not inputs:
            return []

        import torch

        assert self._model is not None
        assert self._tokenizer is not None
        predictions: list[DualTaskPrediction] = []
        for start in range(0, len(inputs), self.batch_size):
            batch = list(inputs[start : start + self.batch_size])
            encoded = self._tokenizer(
                [
                    truncate_turn_node_text(item, self._tokenizer, self.max_length)
                    for item in batch
                ],
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            encoded = {key: value.to(self.device) for key, value in encoded.items()}
            mastery_values = torch.tensor(
                [
                    -1.0
                    if item.current_mastery is None or item.current_mastery < 0
                    else float(item.current_mastery)
                    for item in batch
                ],
                dtype=torch.float32,
                device=self.device,
            ).unsqueeze(-1)

            with torch.inference_mode():
                relevance_logits, change_logits = self._model(
                    current_mastery=mastery_values,
                    **encoded,
                )
                relevance_probabilities = torch.sigmoid(relevance_logits).squeeze(-1).cpu().tolist()
                change_probabilities = torch.softmax(change_logits, dim=-1).cpu().tolist()

            for item, relevance_probability, change_probability in zip(
                batch, relevance_probabilities, change_probabilities
            ):
                predictions.append(
                    DualTaskPrediction(
                        node_id=item.node_id,
                        node_name=item.node_name,
                        relevance_probability=float(relevance_probability),
                        change_probabilities=tuple(float(value) for value in change_probability),  # type: ignore[arg-type]
                    )
                )
        return predictions

    async def predict(self, inputs: Sequence[TurnNodeInput]) -> list[DualTaskPrediction]:
        return await asyncio.to_thread(self._predict_sync, inputs)


@lru_cache(maxsize=4)
def _cached_local_classifier(
    checkpoint_path: str,
    max_length: int,
    batch_size: int,
    device: str,
) -> LocalDualTaskMasteryClassifier:
    """Reuse one loaded checkpoint across background evaluations in a worker."""

    return LocalDualTaskMasteryClassifier(
        checkpoint_path,
        max_length=max_length,
        batch_size=batch_size,
        device=device,
    )


def build_configured_dual_task_classifier(settings) -> DualTaskMasteryClassifier | None:
    """Build the configured classifier, or return ``None`` for LLM-only fallback."""

    if not getattr(settings, "mastery_dual_task_enabled", False):
        return None
    checkpoint_path = str(getattr(settings, "mastery_dual_task_checkpoint_path", "")).strip()
    if not checkpoint_path:
        logger.warning("Dual-task mastery is enabled without a checkpoint; using LLM-only fallback")
        return None
    try:
        return _cached_local_classifier(
            checkpoint_path,
            int(getattr(settings, "mastery_dual_task_max_length", 512)),
            int(getattr(settings, "mastery_dual_task_batch_size", 16)),
            str(getattr(settings, "mastery_dual_task_device", "cpu")),
        )
    except (OSError, TypeError, ValueError) as exc:
        logger.error("Cannot configure dual-task mastery checkpoint: %s", exc)
        return None
