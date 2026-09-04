from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    ConversationKind,
    Edge,
    EdgeType,
    Message,
    MessageRole,
    Node,
    PresentationRevisionStatus,
    PresentationRunStatus,
    Space,
    SpaceMember,
    SpaceMemberRole,
    TeacherPresentationEvent,
    TeacherPresentationRevision,
    User,
)
from teacher.presentations import service
from teacher.presentations.router import get_presentation_messages


async def seed_presentation_course(db: AsyncSession):
    teacher = User(email=f"{uuid4()}@example.com", nickname="Teacher")
    db.add(teacher)
    await db.flush()
    space = Space(
        user_id=teacher.id,
        name="数据结构",
        color="#3366ff",
        is_collaborative=True,
    )
    db.add(space)
    await db.flush()
    db.add(
        SpaceMember(
            space_id=space.id,
            user_id=teacher.id,
            role=SpaceMemberRole.TEACHER,
            can_edit_graph=False,
        )
    )
    await db.commit()
    return teacher, space


class FakeManager:
    def __init__(self):
        self.payload = None

    async def create_run(self, payload):
        self.payload = payload
        return {"run_id": payload["run_id"], "status": "starting"}

    async def resume_run(self, _run_id, payload):
        self.payload = payload
        return {"run_id": payload["run_id"], "status": "starting"}


class FakeStatusManager:
    def __init__(self, status: str, error: str | None = None):
        self.status = status
        self.error = error

    async def get_run(self, _run_id):
        return {"status": self.status, "error": self.error}


@pytest.mark.asyncio
async def test_project_creates_isolated_teacher_presentation_conversation(
    db_session: AsyncSession,
):
    teacher, space = await seed_presentation_course(db_session)
    project = await service.create_project(
        db_session, space_id=space.id, user_id=teacher.id, title="线性表教案"
    )
    conversation = await db_session.get(__import__("db.models", fromlist=["Conversation"]).Conversation, project.conversation_id)
    assert conversation.kind == ConversationKind.TEACHER_PRESENTATION
    assert project.teacher_user_id == teacher.id


@pytest.mark.asyncio
async def test_create_run_scopes_manager_and_rejects_stale_revision(
    db_session: AsyncSession,
):
    teacher, space = await seed_presentation_course(db_session)
    project = await service.create_project(
        db_session, space_id=space.id, user_id=teacher.id, title="图"
    )
    manager = FakeManager()
    run, token = await service.create_run(
        db_session,
        project=project,
        content="生成图的遍历课件",
        gateway_url="http://backend:8000/api/internal/presentation-agent/runs",
        expected_revision_id=None,
        manager=manager,
    )
    assert len(token) >= 48
    assert manager.payload["run_id"] == str(run.id)
    assert manager.payload["instruction"] == "生成图的遍历课件"
    assert manager.payload["max_iterations"] == 60
    assert manager.payload["gateway_url"].endswith(str(run.id))
    assert manager.payload["metadata"]["revision_id"] == str(run.revision_id)

    with pytest.raises(HTTPException) as exc:
        await service.create_run(
            db_session,
            project=project,
            content="过期客户端修改",
            gateway_url="http://backend:8000/api/internal/presentation-agent/runs",
            expected_revision_id=uuid4(),
            manager=manager,
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_course_graph_overview_has_shared_structure_only_and_no_mastery(
    db_session: AsyncSession,
):
    teacher, space = await seed_presentation_course(db_session)
    root = Node(space_id=space.id, label="数据结构", mastery=99)
    child = Node(space_id=space.id, label="线性表", mastery=88)
    db_session.add_all([root, child])
    await db_session.flush()
    db_session.add_all(
        [
            Edge(
                space_id=space.id,
                from_node_id=root.id,
                to_node_id=child.id,
                type=EdgeType.KNOWLEDGE_TREE,
                user_id=None,
            ),
            Edge(
                space_id=space.id,
                from_node_id=child.id,
                to_node_id=root.id,
                type=EdgeType.ADVANCED,
                user_id=None,
            ),
            Edge(
                space_id=space.id,
                from_node_id=root.id,
                to_node_id=child.id,
                type=EdgeType.LEARNING_PATH,
                user_id=teacher.id,
            ),
        ]
    )
    await db_session.commit()

    result = await service.get_course_graph_overview(db_session, space.id)
    assert {edge["type"] for edge in result["edges"]} == {
        "knowledge_tree",
        "advanced",
    }
    assert all("mastery" not in node for node in result["nodes"])
    assert "learning_path" not in str(result)


@pytest.mark.asyncio
async def test_capability_revalidates_token_headers_and_database_scope(
    db_session: AsyncSession,
):
    teacher, space = await seed_presentation_course(db_session)
    project = await service.create_project(
        db_session, space_id=space.id, user_id=teacher.id, title="树"
    )
    manager = FakeManager()
    run, token = await service.create_run(
        db_session,
        project=project,
        content="生成树课件",
        gateway_url="http://backend:8000/api/internal/presentation-agent/runs",
        expected_revision_id=None,
        manager=manager,
    )
    checked_run, checked_project = await service.verify_capability(
        db_session,
        run_id=run.id,
        token=token,
        header_run_id=str(run.id),
        header_project_id=str(project.id),
    )
    assert checked_run.id == run.id
    assert checked_project.id == project.id

    with pytest.raises(HTTPException) as exc:
        await service.verify_capability(
            db_session,
            run_id=run.id,
            token=token,
            header_run_id=str(run.id),
            header_project_id=str(uuid4()),
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_publish_is_confirmed_host_side_upsert_with_history_and_creator(
    db_session: AsyncSession, tmp_path: Path, monkeypatch
):
    teacher, space = await seed_presentation_course(db_session)
    project = await service.create_project(
        db_session, space_id=space.id, user_id=teacher.id, title="排序"
    )
    private_dir = tmp_path / "private"
    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(upload_dir=str(upload_dir), presentation_private_dir=str(private_dir)),
    )
    scheduled = []
    monkeypatch.setattr(service, "schedule_document_processing", scheduled.append)
    output = private_dir / str(project.id) / "revisions" / "deck.pptx"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"pptx-v1")
    first = TeacherPresentationRevision(
        project_id=project.id,
        revision_number=1,
        status=PresentationRevisionStatus.COMPLETED,
        pptx_path=str(output),
    )
    db_session.add(first)
    await db_session.commit()

    publication_one = await service.publish_revision(
        db_session,
        project=project,
        revision=first,
        publisher_user_id=teacher.id,
        title="排序课件",
    )
    document_id = publication_one.document_id
    document = await db_session.get(__import__("db.models", fromlist=["SpaceDocument"]).SpaceDocument, document_id)
    assert document.creator_user_id == teacher.id
    assert document.url.startswith("/uploads/documents/")

    output.write_bytes(b"pptx-v2")
    second = TeacherPresentationRevision(
        project_id=project.id,
        parent_revision_id=first.id,
        revision_number=2,
        status=PresentationRevisionStatus.COMPLETED,
        pptx_path=str(output),
    )
    db_session.add(second)
    await db_session.commit()
    publication_two = await service.publish_revision(
        db_session,
        project=project,
        revision=second,
        publisher_user_id=teacher.id,
        title="排序课件（更新）",
    )
    assert publication_two.document_id == document_id
    assert publication_two.id != publication_one.id
    assert scheduled == [document_id, document_id]


@pytest.mark.asyncio
async def test_agent_publish_tool_can_only_request_teacher_confirmation(
    db_session: AsyncSession,
):
    teacher, space = await seed_presentation_course(db_session)
    project = await service.create_project(
        db_session, space_id=space.id, user_id=teacher.id, title="队列"
    )
    run, _ = await service.create_run(
        db_session,
        project=project,
        content="生成队列课件",
        gateway_url="http://backend:8000/api/internal/presentation-agent/runs",
        expected_revision_id=None,
        manager=FakeManager(),
    )
    revision = await db_session.get(TeacherPresentationRevision, run.revision_id)
    revision.status = PresentationRevisionStatus.COMPLETED
    project.current_revision_id = revision.id
    await db_session.commit()
    result = await service.execute_capability_tool(
        db_session,
        run=run,
        project=project,
        tool_name="publish_presentation_to_space",
        arguments={"confirmed": True, "revision_id": str(revision.id)},
    )
    assert result["success"] is False
    assert result["requires_confirmation"] is True
    assert project.published_document_id is None


@pytest.mark.asyncio
async def test_manager_exit_without_artifact_fails_run_and_emits_error(
    db_session: AsyncSession,
):
    teacher, space = await seed_presentation_course(db_session)
    project = await service.create_project(
        db_session, space_id=space.id, user_id=teacher.id, title="堆"
    )
    run, _ = await service.create_run(
        db_session,
        project=project,
        content="生成堆课件",
        gateway_url="http://backend:8000/api/internal/presentation-agent/runs",
        expected_revision_id=None,
        manager=FakeManager(),
    )

    refreshed = await service.refresh_run_status(
        db_session, run, manager=FakeStatusManager("succeeded")
    )
    revision = await db_session.get(TeacherPresentationRevision, run.revision_id)
    events = list(
        (
            await db_session.scalars(
                select(TeacherPresentationEvent).where(
                    TeacherPresentationEvent.run_id == run.id
                )
            )
        ).all()
    )

    assert refreshed.status == PresentationRunStatus.FAILED
    assert revision.status == PresentationRevisionStatus.FAILED
    assert any(event.event_type == "error" for event in events)


@pytest.mark.asyncio
async def test_terminal_event_persists_ordered_stream_segments_and_qwen_thinking(
    db_session: AsyncSession,
):
    teacher, space = await seed_presentation_course(db_session)
    project = await service.create_project(
        db_session, space_id=space.id, user_id=teacher.id, title="流式课件"
    )
    run, _ = await service.create_run(
        db_session,
        project=project,
        content="先讨论课件",
        gateway_url="http://backend:8000/api/internal/presentation-agent/runs",
        expected_revision_id=None,
        manager=FakeManager(),
    )
    streamed = [
        ("thinking_delta", {"content": "先分析教案", "iteration": 1}),
        ("text_delta", {"content": "我先读取资料。", "iteration": 1}),
        (
            "tool_call",
            {"id": "c1", "name": "read_document", "status": "running", "iteration": 1},
        ),
        (
            "tool_call",
            {
                "id": "c1",
                "name": "read_document",
                "status": "done",
                "arguments": {"document_id": "d1"},
                "result": {"success": True},
                "iteration": 1,
            },
        ),
        ("text_delta", {"content": "资料读取完成。", "iteration": 2}),
    ]
    for sequence, (event_type, payload) in enumerate(streamed, start=2):
        await service.append_event(
            db_session,
            run=run,
            project=project,
            sequence=sequence,
            event_type=event_type,
            payload=payload,
        )
    await service.append_event(
        db_session,
        run=run,
        project=project,
        sequence=7,
        event_type="conversation_complete",
        payload={"message": "资料读取完成。", "artifact_ready": False},
    )

    assistant = await db_session.scalar(
        select(Message)
        .where(
            Message.conversation_id == project.conversation_id,
            Message.role == MessageRole.ASSISTANT,
        )
        .order_by(Message.created_at.desc())
    )
    assert assistant.llm_context["thinking_content"] == "先分析教案"
    assert assistant.llm_context["thinking_duration"] >= 0
    assert [item["type"] for item in assistant.llm_context["segments"]] == [
        "text",
        "tool",
        "text",
    ]
    assert assistant.llm_context["segments"][1]["status"] == "done"
    assert assistant.tool_calls[0]["arguments"] == {"document_id": "d1"}
    assert assistant.content == "我先读取资料。\n\n资料读取完成。"


@pytest.mark.asyncio
async def test_failed_run_persists_partial_assistant_and_marks_running_tool_interrupted(
    db_session: AsyncSession,
):
    teacher, space = await seed_presentation_course(db_session)
    project = await service.create_project(
        db_session, space_id=space.id, user_id=teacher.id, title="可恢复课件"
    )
    run, _ = await service.create_run(
        db_session,
        project=project,
        content="制作链表课件",
        gateway_url="http://backend:8000/api/internal/presentation-agent/runs",
        expected_revision_id=None,
        manager=FakeManager(),
    )
    await service.append_event(
        db_session,
        run=run,
        project=project,
        sequence=2,
        event_type="text_delta",
        payload={"content": "正在创建课件。", "iteration": 1},
    )
    await service.append_event(
        db_session,
        run=run,
        project=project,
        sequence=3,
        event_type="tool_call",
        payload={"id": "build-1", "name": "execute_command", "status": "running"},
    )
    await service.append_event(
        db_session,
        run=run,
        project=project,
        sequence=4,
        event_type="error",
        payload={"message": "ReadTimeout", "error_type": "ReadTimeout", "stage": "tool"},
    )

    assistant = await db_session.scalar(
        select(Message).where(
            Message.conversation_id == project.conversation_id,
            Message.role == MessageRole.ASSISTANT,
        )
    )
    assert assistant.llm_context["run_id"] == str(run.id)
    assert assistant.llm_context["run_status"] == "failed"
    assert assistant.llm_context["segments"][-1]["status"] == "error"
    assert assistant.llm_context["stream_sequence"] == 4


@pytest.mark.asyncio
async def test_attempt_failure_recovers_same_run_and_manual_resume_rotates_token(
    db_session: AsyncSession,
):
    teacher, space = await seed_presentation_course(db_session)
    project = await service.create_project(
        db_session, space_id=space.id, user_id=teacher.id, title="恢复"
    )
    manager = FakeManager()
    run, _ = await service.create_run(
        db_session,
        project=project,
        content="制作树课件",
        gateway_url="http://backend:8000/api/internal/presentation-agent/runs",
        expected_revision_id=None,
        manager=manager,
    )
    await service.append_event(
        db_session,
        run=run,
        project=project,
        sequence=2,
        event_type="attempt_failed",
        payload={"message": "network timeout", "attempt": 1, "retryable": True},
    )
    assert run.status == PresentationRunStatus.RECOVERING

    await service.append_event(
        db_session,
        run=run,
        project=project,
        sequence=3,
        event_type="error",
        payload={"message": "retry budget exhausted"},
    )
    old_hash = run.capability_token_hash
    resumed = await service.resume_run(
        db_session,
        project=project,
        run_id=run.id,
        gateway_url="http://backend:8000/api/internal/presentation-agent/runs",
        manager=manager,
    )
    assert resumed.id == run.id
    assert resumed.status == PresentationRunStatus.RECOVERING
    assert resumed.capability_token_hash != old_hash
    assert manager.payload["run_id"] == str(run.id)
    assert manager.payload["reset_iterations"] is True


@pytest.mark.asyncio
async def test_active_run_history_is_synthesized_from_durable_events(
    db_session: AsyncSession,
):
    teacher, space = await seed_presentation_course(db_session)
    project = await service.create_project(
        db_session, space_id=space.id, user_id=teacher.id, title="刷新恢复"
    )
    run, _ = await service.create_run(
        db_session,
        project=project,
        content="制作队列课件",
        gateway_url="http://backend:8000/api/internal/presentation-agent/runs",
        expected_revision_id=None,
        manager=FakeManager(),
    )
    await service.append_event(
        db_session,
        run=run,
        project=project,
        sequence=2,
        event_type="thinking_delta",
        payload={"content": "正在规划页面", "iteration": 1},
    )
    await service.append_event(
        db_session,
        run=run,
        project=project,
        sequence=3,
        event_type="text_delta",
        payload={"content": "我先读取课程内容。", "iteration": 1},
    )

    messages = await get_presentation_messages(
        space_id=space.id,
        project_id=project.id,
        user=teacher,
        db=db_session,
    )
    assistant = next(message for message in messages if message.role == "assistant")
    assert assistant.run_id == run.id
    assert assistant.streaming is True
    assert assistant.stream_sequence == 3
    assert assistant.llm_context["thinking_content"] == "正在规划页面"


@pytest.mark.asyncio
async def test_conversation_complete_without_artifact_can_resume_same_draft_run(
    db_session: AsyncSession,
):
    teacher, space = await seed_presentation_course(db_session)
    project = await service.create_project(
        db_session, space_id=space.id, user_id=teacher.id, title="恢复待验收文件"
    )
    manager = FakeManager()
    run, _ = await service.create_run(
        db_session,
        project=project,
        content="制作链表课件",
        gateway_url="http://backend:8000/api/internal/presentation-agent/runs",
        expected_revision_id=None,
        manager=manager,
    )
    await service.append_event(
        db_session,
        run=run,
        project=project,
        sequence=2,
        event_type="conversation_complete",
        payload={"message": "检查结束", "artifact_ready": False},
    )

    resumed = await service.resume_run(
        db_session,
        project=project,
        run_id=run.id,
        gateway_url="http://backend:8000/api/internal/presentation-agent/runs",
        manager=manager,
    )

    assert resumed.status == PresentationRunStatus.RECOVERING
    assert manager.payload["reset_iterations"] is True


@pytest.mark.asyncio
async def test_presentation_ready_event_persists_revision_metadata(
    db_session: AsyncSession,
):
    teacher, space = await seed_presentation_course(db_session)
    project = await service.create_project(
        db_session, space_id=space.id, user_id=teacher.id, title="完成事件"
    )
    run, _ = await service.create_run(
        db_session,
        project=project,
        content="制作课件",
        gateway_url="http://backend:8000/api/internal/presentation-agent/runs",
        expected_revision_id=None,
        manager=FakeManager(),
    )
    revision = await db_session.get(TeacherPresentationRevision, run.revision_id)
    revision.pptx_path = "/private/already-uploaded.pptx"
    revision.preview_manifest = {"pages": [{"page": 1, "asset_id": str(uuid4())}]}
    await db_session.commit()

    event = await service.append_event(
        db_session,
        run=run,
        project=project,
        sequence=2,
        event_type="presentation_ready",
        payload={"message": "完成"},
    )

    assert event.payload["revision_id"] == str(revision.id)
    assert event.payload["revision_number"] == revision.revision_number
    assert event.payload["preview_manifest"]["pages"][0]["page"] == 1
