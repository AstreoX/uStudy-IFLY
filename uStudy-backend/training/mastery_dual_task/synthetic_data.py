"""Deterministic synthetic learner-dialogue data for pipeline pretraining.

The generated corpus is intentionally a training-pipeline bootstrap, not evidence of
real learner-modeling quality. Splits are made by learner ID before any samples are
written so a learner never appears in more than one subset.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

from graph.mastery_dual_task import build_turn_node_input


@dataclass(frozen=True)
class Concept:
    name: str
    parent: str
    correct_fact: str
    localized_error: str
    fundamental_error: str


CONCEPTS: tuple[Concept, ...] = (
    Concept("数组", "线性表", "数组使用连续存储并支持按下标随机访问", "数组插入元素通常需要移动后续元素，但并非所有插入都是常数时间", "数组的元素通过指针随机散落，因此只能顺序访问"),
    Concept("链表", "线性表", "链表节点通过指针连接，定位第 k 个节点通常需要顺序遍历", "链表在已知位置插入可为常数时间，但查找插入位置仍可能是线性时间", "链表存储连续，所以能够像数组一样按下标常数访问"),
    Concept("栈", "栈和队列", "栈遵循后进先出，入栈和出栈都发生在栈顶", "顺序栈扩容可能产生线性开销，但普通栈顶操作通常是常数时间", "栈遵循先进先出并从队头删除元素"),
    Concept("队列", "栈和队列", "队列通常遵循先进先出，从队尾入队并从队头出队", "循环队列判空判满需要约定，但并不要求移动全部元素", "队列遵循后进先出并且所有操作都在同一端完成"),
    Concept("二叉树", "树", "二叉树每个节点至多有两个孩子，左右子树具有次序", "二叉树不一定是完全二叉树，也不保证所有层都填满", "二叉树的每个节点必须恰好有两个孩子"),
    Concept("二叉搜索树", "树", "二叉搜索树中左子树键值较小、右子树键值较大，中序遍历有序", "普通二叉搜索树最坏会退化为链表，查找不总是对数时间", "二叉搜索树通过层序遍历保证键值自动有序"),
    Concept("前序遍历", "树的遍历", "前序遍历按根节点、左子树、右子树的顺序访问", "前序和中序顺序不同，不能把根节点固定放在中间", "前序遍历按照左子树、右子树、根节点访问"),
    Concept("广度优先搜索", "图", "广度优先搜索借助队列按层扩展顶点", "在无权图中 BFS 可求最少边数路径，但不直接解决一般带权最短路", "广度优先搜索使用栈并沿单一路径一直深入"),
    Concept("深度优先搜索", "图", "深度优先搜索使用递归或栈沿分支深入后回溯", "DFS 能判断连通性，但首次到达路径不保证是无权图最短路径", "深度优先搜索依靠队列逐层访问所有相邻顶点"),
    Concept("散列表", "查找", "散列表通过散列函数定位桶，并使用开放定址或链地址处理冲突", "平均查找可接近常数时间，但冲突严重时性能会下降", "散列表永远不会发生冲突，因此查找复杂度固定为常数"),
    Concept("二分查找", "查找", "二分查找要求序列有序，每次排除一半搜索区间", "二分查找通常需要随机访问结构，不适合直接在普通链表上获得对数访问", "二分查找可直接用于任意无序序列并保证找到目标"),
    Concept("快速排序", "排序", "快速排序通过枢轴划分后递归处理两侧子序列", "快速排序平均复杂度为 O(n log n)，但最坏可达到 O(n²)", "快速排序在任何输入上都稳定且最坏复杂度为 O(n log n)"),
    Concept("归并排序", "排序", "归并排序先递归划分，再线性合并有序子序列", "归并排序时间复杂度稳定为 O(n log n)，但数组实现通常需要额外空间", "归并排序完全原地且不需要任何辅助空间"),
    Concept("堆排序", "排序", "堆排序利用完全二叉树形式的堆反复选择极值", "堆排序为 O(n log n)，但通常不是稳定排序", "堆排序只能处理已经有序的数据"),
    Concept("时间复杂度", "算法分析", "时间复杂度描述输入规模增长时基本操作次数的渐近增长", "常数因子通常在渐近记号中省略，但实际性能仍可能受其影响", "时间复杂度等同于程序在某台电脑上运行的精确秒数"),
)

CHANGE_CODES: tuple[int, ...] = (-2, -1, 0, 1, 2)


@dataclass(frozen=True)
class SyntheticSample:
    learner_id: str
    turn_id: str
    node_id: str
    node_name: str
    current_mastery: int
    serialized_text: str
    relevance_label: int
    change_label: int


def _course_graph() -> tuple[list[dict], list[dict]]:
    parent_names = sorted({concept.parent for concept in CONCEPTS})
    nodes = [{"id": "course", "label": "数据结构", "mastery": 0}]
    nodes.extend(
        {"id": f"parent-{index}", "label": name, "mastery": 0}
        for index, name in enumerate(parent_names)
    )
    nodes.extend(
        {"id": f"concept-{index}", "label": concept.name, "mastery": 0}
        for index, concept in enumerate(CONCEPTS)
    )
    id_by_label = {node["label"]: node["id"] for node in nodes}
    edges: list[dict] = []
    for parent in parent_names:
        edges.append(
            {
                "from_node_id": "course",
                "to_node_id": id_by_label[parent],
                "type": "knowledge_tree",
            }
        )
    for concept in CONCEPTS:
        edges.append(
            {
                "from_node_id": id_by_label[concept.parent],
                "to_node_id": id_by_label[concept.name],
                "type": "knowledge_tree",
            }
        )
    for first, second in zip(CONCEPTS, CONCEPTS[1:]):
        edges.append(
            {
                "from_node_id": id_by_label[first.name],
                "to_node_id": id_by_label[second.name],
                "type": "learning_path",
            }
        )
    for source, target in (("数组", "二分查找"), ("队列", "广度优先搜索"), ("栈", "深度优先搜索"), ("二叉树", "堆排序")):
        edges.append(
            {
                "from_node_id": id_by_label[source],
                "to_node_id": id_by_label[target],
                "type": "advanced",
            }
        )
    return nodes, edges


def _response_for(concepts: Sequence[Concept], change_code: int, rng: random.Random) -> str:
    names = "和".join(concept.name for concept in concepts)
    if change_code == -2:
        claims = "；".join(concept.fundamental_error for concept in concepts)
        return rng.choice((f"我认为{claims}。所以{names}的核心规则就是这样。", f"答案很明确：{claims}。"))
    if change_code == -1:
        claims = "；".join(concept.localized_error for concept in concepts)
        return rng.choice((f"我的理解是：{claims}。", f"{names}的大方向我明白，不过我觉得{claims}。"))
    if change_code == 0:
        return rng.choice((f"这应该和{names}有关，但我还不能确定具体推理。", f"我记得{names}有这些概念，不过目前证据有点混合。"))
    if change_code == 1:
        claims = "；".join(concept.correct_fact for concept in concepts)
        return rng.choice((f"{claims}。", f"核心点是：{claims}，但细节我暂时不展开。"))
    claims = "；".join(concept.correct_fact for concept in concepts)
    application = rng.choice(("因此可以据此分析操作复杂度", "我还能用一个小例子逐步验证这个过程", "实际实现时也应保持这些不变量"))
    return f"{claims}。{application}，结论与定义一致。"


def generate_synthetic_corpus(
    *,
    learner_count: int = 50,
    turns_per_learner: int = 12,
    candidates_per_turn: int = 5,
    seed: int = 42,
) -> list[SyntheticSample]:
    """Generate balanced five-class samples and roughly 1/3 relevant pairs."""

    if learner_count < 3:
        raise ValueError("learner_count must be at least 3")
    if turns_per_learner < 5:
        raise ValueError("turns_per_learner must be at least 5")
    if not 3 <= candidates_per_turn <= len(CONCEPTS):
        raise ValueError("candidates_per_turn must be between 3 and the concept count")

    rng = random.Random(seed)
    base_nodes, edges = _course_graph()
    samples: list[SyntheticSample] = []

    for learner_index in range(learner_count):
        learner_id = f"synthetic-{learner_index + 1:03d}"
        learner_rng = random.Random(rng.randint(0, 10_000_000))
        for turn_index in range(turns_per_learner):
            change_code = CHANGE_CODES[(learner_index + turn_index) % len(CHANGE_CODES)]
            primary_index = (learner_index * 3 + turn_index) % len(CONCEPTS)
            relevant_concepts = [CONCEPTS[primary_index]]
            if turn_index % 3 != 0:
                relevant_concepts.append(CONCEPTS[(primary_index + 1) % len(CONCEPTS)])

            irrelevant_pool = [concept for concept in CONCEPTS if concept not in relevant_concepts]
            irrelevant_concepts = learner_rng.sample(
                irrelevant_pool,
                candidates_per_turn - len(relevant_concepts),
            )
            candidates = relevant_concepts + irrelevant_concepts
            learner_rng.shuffle(candidates)

            instruction = f"请说明{'和'.join(concept.name for concept in relevant_concepts)}的核心原理，并给出判断依据。"
            response = _response_for(relevant_concepts, change_code, learner_rng)
            conversation = [
                {"role": "assistant", "content": instruction},
                {"role": "user", "content": response},
            ]
            mastery_by_name = {
                concept.name: learner_rng.choice((-1, 0, 20, 35, 50, 65, 80))
                for concept in candidates
            }
            nodes = [dict(node) for node in base_nodes]
            for node in nodes:
                if node["label"] in mastery_by_name:
                    node["mastery"] = mastery_by_name[node["label"]]
            node_by_name = {node["label"]: node for node in nodes}

            relevant_names = {concept.name for concept in relevant_concepts}
            for concept in candidates:
                candidate = node_by_name[concept.name]
                turn_node_input = build_turn_node_input(
                    conversation,
                    candidate,
                    nodes,
                    edges,
                )
                is_relevant = concept.name in relevant_names
                samples.append(
                    SyntheticSample(
                        learner_id=learner_id,
                        turn_id=f"{learner_id}-turn-{turn_index + 1:02d}",
                        node_id=str(candidate["id"]),
                        node_name=concept.name,
                        current_mastery=int(candidate["mastery"]),
                        serialized_text=turn_node_input.serialized_text,
                        relevance_label=int(is_relevant),
                        change_label=change_code if is_relevant else 0,
                    )
                )
    return samples


def split_by_learner(
    samples: Sequence[SyntheticSample],
    *,
    train_learners: int = 35,
    validation_learners: int = 7,
    test_learners: int = 8,
    seed: int = 42,
) -> dict[str, list[SyntheticSample]]:
    """Apply the SI learner-level 35/7/8 split without leakage."""

    learner_ids = sorted({sample.learner_id for sample in samples})
    if len(learner_ids) != train_learners + validation_learners + test_learners:
        raise ValueError("Split sizes must equal the number of unique learners")
    random.Random(seed).shuffle(learner_ids)
    train_ids = set(learner_ids[:train_learners])
    validation_ids = set(learner_ids[train_learners : train_learners + validation_learners])
    test_ids = set(learner_ids[-test_learners:])
    return {
        "train": [sample for sample in samples if sample.learner_id in train_ids],
        "validation": [sample for sample in samples if sample.learner_id in validation_ids],
        "test": [sample for sample in samples if sample.learner_id in test_ids],
    }


def _split_stats(samples: Sequence[SyntheticSample]) -> dict:
    relevant = [sample for sample in samples if sample.relevance_label == 1]
    return {
        "sample_count": len(samples),
        "learner_count": len({sample.learner_id for sample in samples}),
        "relevant_count": len(relevant),
        "relevance_ratio": len(relevant) / len(samples) if samples else 0.0,
        "relevant_change_distribution": dict(
            sorted(Counter(sample.change_label for sample in relevant).items())
        ),
    }


def write_synthetic_dataset(output_dir: str | Path, splits: dict[str, list[SyntheticSample]]) -> dict:
    """Write JSONL splits and a manifest with leakage and balance checks."""

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    learner_sets = {
        split_name: {sample.learner_id for sample in split_samples}
        for split_name, split_samples in splits.items()
    }
    if learner_sets["train"] & learner_sets["validation"]:
        raise ValueError("Learner leakage between train and validation")
    if learner_sets["train"] & learner_sets["test"]:
        raise ValueError("Learner leakage between train and test")
    if learner_sets["validation"] & learner_sets["test"]:
        raise ValueError("Learner leakage between validation and test")

    for split_name, split_samples in splits.items():
        with (output / f"{split_name}.jsonl").open("w", encoding="utf-8") as stream:
            for sample in split_samples:
                stream.write(json.dumps(asdict(sample), ensure_ascii=False) + "\n")

    manifest = {
        "synthetic_only": True,
        "seed": 42,
        "split_policy": "learner-level 35/7/8",
        "splits": {
            split_name: _split_stats(split_samples)
            for split_name, split_samples in splits.items()
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest
