from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from db.models import PresentationRunStatus
from teacher.presentations import service
from teacher.presentations.errors import normalize_run_error
from teacher.presentations.router import get_presentation_messages
from tests.teacher.test_teacher_presentations import FakeManager, seed_presentation_course


async def create(db):
    teacher, space = await seed_presentation_course(db)
    project = await service.create_project(db, space_id=space.id, user_id=teacher.id, title="Binary tree")
    run, token = await service.create_run(db, project=project, content="make deck", gateway_url="http://backend/runs", manager=FakeManager())
    return teacher, space, project, run, token


async def verify(db, project, run, token, **overrides):
    params = dict(run_id=run.id, token=token, header_run_id=str(run.id), header_project_id=str(project.id))
    params.update(overrides)
    return await service.verify_capability(db, **params)


@pytest.mark.asyncio
async def test_active_capability_renews_across_multiple_six_hour_windows(db_session, monkeypatch):
    _, _, project, run, token = await create(db_session)
    start = service.utcnow()
    for hour in (5.5, 11, 16.5):
        now = start + timedelta(hours=hour)
        monkeypatch.setattr(service, "utcnow", lambda: now)
        await verify(db_session, project, run, token)
        await db_session.refresh(run)
        assert service._as_aware(run.capability_expires_at) == now + timedelta(hours=6)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["expired", "wrong_token", "wrong_project", "permission"])
async def test_invalid_capability_does_not_renew(db_session, monkeypatch, failure):
    _, _, project, run, token = await create(db_session)
    run.capability_expires_at = service.utcnow() + timedelta(minutes=-1 if failure == "expired" else 30)
    await db_session.commit()
    before = run.capability_expires_at
    overrides = {}
    if failure == "wrong_token": token = "invalid"
    if failure == "wrong_project": overrides["header_project_id"] = str(uuid4())
    if failure == "permission":
        async def denied(*args): return False
        monkeypatch.setattr(service, "has_course_teacher_access", denied)
    with pytest.raises(HTTPException) as exc:
        await verify(db_session, project, run, token, **overrides)
    assert exc.value.status_code in (401, 403)
    assert run.capability_expires_at == before


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [PresentationRunStatus.COMPLETED, PresentationRunStatus.FAILED, PresentationRunStatus.CANCELLED])
async def test_terminal_task_does_not_renew(db_session, status):
    _, _, project, run, token = await create(db_session)
    run.status = status
    run.capability_expires_at = service.utcnow() + timedelta(minutes=30)
    await db_session.commit()
    before = run.capability_expires_at
    await verify(db_session, project, run, token)
    assert run.capability_expires_at == before


def test_error_classification_separates_retry_and_manual_resume():
    old = normalize_run_error({"message": "maximum presentation-agent iterations reached", "retryable": False})
    assert old["recoverable"] and not old["retryable"]
    assert old["error_code"] == "legacy_iteration_limit"
    assert normalize_run_error({"reason": "runtime_dependencies"})["recoverable"] is False
    assert normalize_run_error({"message": "unknown"})["error_code"] != "runtime_dependencies"
    assert normalize_run_error({"retryable": False, "recoverable": True})["recoverable"] is True


@pytest.mark.asyncio
async def test_legacy_failure_can_resume_same_run_without_reset(db_session):
    teacher, space, project, run, _ = await create(db_session)
    await service.append_event(db_session, run=run, project=project, sequence=None, event_type="error",
                               payload={"message": "maximum presentation-agent iterations reached", "retryable": False})
    messages = await get_presentation_messages(space_id=space.id, project_id=project.id, user=teacher, db=db_session)
    error_message = next(message for message in messages if message.role == "assistant")
    assert error_message.recoverable is True
    assert error_message.error_code == "legacy_iteration_limit"
    assert error_message.run_error == "任务因旧版执行轮次限制停止，可继续执行。"
    run_id, revision_id = run.id, run.revision_id
    manager = FakeManager()
    await service.resume_run(db_session, project=project, run_id=run.id, gateway_url="http://backend/runs", manager=manager)
    assert run.id == run_id and run.revision_id == revision_id
    assert run.retry_deadline_at is None
    assert not {"max_iterations", "max_seconds", "reset_iterations"} & manager.payload.keys()
    resumed_messages = await get_presentation_messages(space_id=space.id, project_id=project.id, user=teacher, db=db_session)
    resumed_message = next(message for message in resumed_messages if message.role == "assistant")
    assert resumed_message.streaming is True
    assert resumed_message.run_error is None and resumed_message.error_code is None
    assert "任务未完成" not in resumed_message.content
    assert "maximum presentation-agent iterations reached" not in str(resumed_message.llm_context)
