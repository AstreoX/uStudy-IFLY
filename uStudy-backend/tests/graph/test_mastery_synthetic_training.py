"""Data-contract tests for synthetic dual-task pretraining."""

import numpy as np

from training.mastery_dual_task.synthetic_data import (
    generate_synthetic_corpus,
    split_by_learner,
)
from training.mastery_dual_task.train_synthetic import select_relevance_threshold


def test_synthetic_corpus_has_si_split_without_learner_leakage():
    samples = generate_synthetic_corpus()
    splits = split_by_learner(samples)

    assert len(samples) == 3000
    assert {name: len(rows) for name, rows in splits.items()} == {
        "train": 2100,
        "validation": 420,
        "test": 480,
    }
    learner_sets = {
        name: {sample.learner_id for sample in rows}
        for name, rows in splits.items()
    }
    assert {name: len(ids) for name, ids in learner_sets.items()} == {
        "train": 35,
        "validation": 7,
        "test": 8,
    }
    assert learner_sets["train"].isdisjoint(learner_sets["validation"])
    assert learner_sets["train"].isdisjoint(learner_sets["test"])
    assert learner_sets["validation"].isdisjoint(learner_sets["test"])


def test_synthetic_relevance_and_five_classes_are_balanced():
    samples = generate_synthetic_corpus()
    relevant = [sample for sample in samples if sample.relevance_label == 1]
    distribution = {
        label: sum(sample.change_label == label for sample in relevant)
        for label in (-2, -1, 0, 1, 2)
    }

    assert len(relevant) / len(samples) == 1 / 3
    assert max(distribution.values()) - min(distribution.values()) <= 2
    assert all("[Candidate Node]" in sample.serialized_text for sample in samples[:20])
    assert all("mastery" not in sample.serialized_text.casefold() for sample in samples[:20])


def test_validation_threshold_selection_maximizes_macro_f1():
    labels = np.asarray([0, 0, 1, 1])
    probabilities = np.asarray([0.1, 0.2, 0.8, 0.9])

    threshold, macro_f1 = select_relevance_threshold(labels, probabilities)

    assert 0.21 <= threshold <= 0.8
    assert macro_f1 == 1.0
