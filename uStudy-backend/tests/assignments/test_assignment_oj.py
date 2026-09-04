from uuid import uuid4

import pytest
from pydantic import ValidationError

from assignments.grading import grade_code_answer
from assignments.oj import sanitize_run_result
from assignments.schemas import OjCodeAnswer, OjProblemWriteRequest, OjPublicConfig
from config import Settings


def test_backend_resolves_manager_token_from_persistent_file(tmp_path):
    token_file = tmp_path / "manager-token"
    token_file.write_text("m" * 64, encoding="utf-8")
    settings = Settings(oj_manager_token_file=str(token_file))
    assert settings.oj_manager_token_resolved == "m" * 64

    settings = Settings(
        oj_manager_token="override-token",
        oj_manager_token_file=str(token_file),
    )
    assert settings.oj_manager_token_resolved == "override-token"


def test_public_config_accepts_legacy_float_tolerance_but_serializes_canonical_fields():
    config = OjPublicConfig.model_validate({
        "allowed_languages": ["python3"],
        "default_language": "python3",
        "float_tolerance": 1e-5,
        "samples": [{"input": "1\n", "output": "1\n"}],
    })
    payload = config.model_dump()
    assert payload["float_absolute_tolerance"] == pytest.approx(1e-5)
    assert payload["float_relative_tolerance"] == pytest.approx(1e-5)
    assert "float_tolerance" not in payload


def test_public_samples_have_utf8_byte_and_aggregate_limits():
    with pytest.raises(ValidationError):
        OjPublicConfig(samples=[{"input": "数" * 30_000, "output": ""}])
    with pytest.raises(ValidationError):
        OjPublicConfig(samples=[{"input": "a" * 65536, "output": "b" * 65536}] * 3)


def test_source_limit_is_measured_in_utf8_bytes():
    with pytest.raises(ValidationError):
        OjCodeAnswer(language="python3", source="数" * 30_000)
    with pytest.raises(ValidationError):
        OjPublicConfig(
            allowed_languages=["python3"], default_language="python3",
            starter_code={"python3": "数" * 30_000},
            samples=[{"input": "1\n", "output": "1\n"}],
        )


def test_hidden_group_weights_must_total_one_hundred():
    with pytest.raises(ValidationError):
        OjProblemWriteRequest(
            public_config=OjPublicConfig(samples=[{"input": "", "output": "1\n"}]),
            reference_solution={"language": "python3", "source": "print(1)"},
            hidden_groups=[{
                "name": "基础", "weight": 90,
                "cases": [{"input": "", "expected_output": "1\n"}],
            }],
        )


def test_final_result_sanitizer_never_exposes_hidden_case_payloads():
    sanitized = sanitize_run_result({
        "status": "completed",
        "verdict": "wrong_answer",
        "score": 5,
        "group_results": [{
            "name": "边界", "verdict": "wrong_answer", "score": 0,
            "input": "SECRET", "expected_output": "SECRET", "actual_output": "leak",
            "time_ms": 5,
        }],
        "samples": [{"input": "SECRET"}],
        "stdout": "SECRET",
    }, include_samples=False)
    assert sanitized["groups"] == [{
        "name": "边界", "verdict": "wrong_answer", "score": 0, "time_ms": 5,
    }]
    assert "samples" not in sanitized
    assert "stdout" not in sanitized
    assert "SECRET" not in str(sanitized)


def test_sample_result_sanitizer_keeps_public_stdout():
    sanitized = sanitize_run_result({
        "status": "completed", "verdict": "accepted",
        "samples": [{
            "input": "1\n", "expected_output": "1\n", "stdout": "1\n",
            "stderr": "", "verdict": "accepted",
        }],
    }, include_samples=True)
    assert sanitized["samples"][0]["stdout"] == "1\n"


@pytest.mark.asyncio
async def test_empty_code_answer_is_deterministic_zero_without_manager(monkeypatch):
    class ForbiddenClient:
        def __init__(self):
            raise AssertionError("manager must not be called for an empty answer")

    monkeypatch.setattr("assignments.grading.OjClient", ForbiddenClient)
    result = await grade_code_answer(
        {
            "id": uuid4(), "max_score": 20,
            "grader_config": {"problem_version_id": "v1"},
        },
        {"language": "python3", "source": "   "},
        submission_id=uuid4(),
    )
    assert result.score == 0
    assert result.status == "wrong_answer"
    assert result.grader_result == {"verdict": "wrong_answer", "groups": []}


@pytest.mark.asyncio
async def test_code_answer_uses_versioned_final_run_and_weighted_score(monkeypatch):
    captured = {}

    class FakeClient:
        async def create_run(self, payload):
            captured.update(payload)
            return {"run_id": "manager-1", "status": "queued"}

        async def wait_run(self, run_id):
            assert run_id == "manager-1"
            return {
                "run_id": run_id, "status": "completed", "verdict": "wrong_answer",
                "score": 12.5,
                "group_results": [{
                    "name": "基础", "verdict": "accepted", "score": 12.5,
                    "input": "HIDDEN", "expected_output": "HIDDEN",
                }],
            }

    monkeypatch.setattr("assignments.grading.OjClient", FakeClient)
    result = await grade_code_answer(
        {
            "id": uuid4(), "max_score": 20,
            "grader_config": {"problem_version_id": "version-7"},
        },
        {"language": "cpp20", "source": "int main(){}"},
        submission_id=uuid4(),
    )
    assert captured["run_type"] == "final"
    assert captured["problem_version_id"] == "version-7"
    assert "problem_draft_id" not in captured
    assert result.score == pytest.approx(12.5)
    assert result.status == "wrong_answer"
    assert "HIDDEN" not in str(result.grader_result)


@pytest.mark.asyncio
async def test_code_answer_fetches_full_result_after_terminal_idempotent_ack(monkeypatch):
    calls = []

    class FakeClient:
        async def create_run(self, payload):
            return {"run_id": "existing-run", "status": "completed"}

        async def wait_run(self, run_id):
            calls.append(run_id)
            return {
                "run_id": run_id,
                "status": "completed",
                "verdict": "accepted",
                "score": 10,
                "group_results": [],
            }

    monkeypatch.setattr("assignments.grading.OjClient", FakeClient)
    result = await grade_code_answer(
        {
            "id": uuid4(),
            "max_score": 10,
            "grader_config": {"problem_version_id": "version-1"},
        },
        {"language": "python3", "source": "print(1)"},
        submission_id=uuid4(),
    )

    assert calls == ["existing-run"]
    assert result.status == "accepted"
    assert result.score == pytest.approx(10)
