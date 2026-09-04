import json

import pytest

from assignments.tasks import (
    NonRetryableAssignmentJobError,
    _extract_generation_questions,
    _normalize_generated_oj_question,
)


def test_extract_generation_questions_accepts_json_and_fenced_json():
    question = {
        "question_type": "single_choice",
        "question_stem": "栈的特点是什么？",
        "options": ["先进后出", "先进先出"],
        "correct_answer": {"index": 0},
    }

    response = json.dumps({"questions": [question]}, ensure_ascii=False)
    assert _extract_generation_questions(response)[0]["question_type"] == "single_choice"
    assert _extract_generation_questions(
        "结果如下：\n```json\n{\"questions\": [{\"question_type\": \"true_false\"}]}\n```"
    )[0]["question_type"] == "true_false"


def test_extract_generation_questions_accepts_trailing_prose():
    result = _extract_generation_questions(
        '{"questions":[{"question_type":"short_answer"}]}\n以上是题目。'
    )
    assert result == [{"question_type": "short_answer"}]


@pytest.mark.parametrize("response", ["", "{\"strengths\": []}", '{"questions": []}', '{"questions": ['])
def test_extract_generation_questions_rejects_incomplete_contract(response):
    with pytest.raises(NonRetryableAssignmentJobError, match="AI"):
        _extract_generation_questions(response)


def test_normalize_generated_oj_question_accepts_common_cpp_aliases():
    question = _normalize_generated_oj_question({
        "question_type": "code",
        "public_config": {
            "allowed_languages": ["cpp"],
            "default_language": "C++20",
            "starter_code": "int main() {}",
            "comparison_mode": "standard",
            "samples": [{"input": "1\n", "output": "1\n"}],
        },
        "correct_answer": {
            "solution": {"language": "GNU C++20", "code": "int main() {}"},
        },
        "oj_problem": {
            "reference_solution": "int main() {}",
            "test_groups": [{
                "name": "基础",
                "weight": 100,
                "tests": [{"input": "1\n", "output": "1\n"}],
            }],
        },
    })

    assert question["public_config"]["allowed_languages"] == ["cpp20"]
    assert question["public_config"]["default_language"] == "cpp20"
    assert question["public_config"]["starter_code"] == {"cpp20": "int main() {}"}
    assert question["public_config"]["compare_mode"] == "standard"
    assert question["correct_answer"]["reference_solution"]["language"] == "cpp20"
    assert question["correct_answer"]["reference_solution"]["source"] == "int main() {}"
    assert question["oj_problem"]["reference_solution"]["language"] == "cpp20"
    hidden_case = question["oj_problem"]["hidden_groups"][0]["cases"][0]
    assert hidden_case["expected_output"] == "1\n"
