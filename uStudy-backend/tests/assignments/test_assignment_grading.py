
import pytest

from assignments.grading import score_objective


@pytest.mark.parametrize(
    ("question_type", "answer", "correct", "max_score", "expected", "status"),
    [
        ("single_choice", {"index": 1}, {"index": 1}, 3, 3, "correct"),
        ("single_choice", {"index": 0}, {"index": 1}, 3, 0, "wrong"),
        ("true_false", {"value": False}, {"value": False}, 2, 2, "correct"),
        ("multiple_choice", {"indices": [0, 2]}, {"indices": [0, 2]}, 6, 6, "correct"),
        ("multiple_choice", {"indices": [0]}, {"indices": [0, 2]}, 6, 3, "partial"),
        ("multiple_choice", {"indices": [0, 1]}, {"indices": [0, 2]}, 6, 0, "wrong"),
        ("multiple_choice", {"indices": []}, {"indices": [0, 2]}, 6, 0, "wrong"),
    ],
)
def test_objective_scoring_uses_configured_points(
    question_type, answer, correct, max_score, expected, status
):
    result = score_objective(question_type, answer, correct, max_score)
    assert result.question_id.int == 0
    assert result.score == pytest.approx(expected)
    assert result.status == status


def test_objective_scoring_rejects_unknown_type():
    with pytest.raises(ValueError, match="unsupported"):
        score_objective("code", {"source": "..."}, {}, 10)
