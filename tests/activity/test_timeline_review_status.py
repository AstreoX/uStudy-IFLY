"""Tests for timeline review status tags."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

import activity.router as activity_router_module
from activity.router import get_activity_timeline


@dataclass
class _FakeActivity:
    id: object
    title: str
    summary: str
    activity_type: str
    subject_name: str | None
    related_node_labels: list[str] | None
    message_count: int
    study_depth: str | None
    source: str
    activity_date: date
    activity_time: datetime
    conversation_id: object | None = None
    space_id: object | None = None


@dataclass
class _NextReviewRow:
    activity_id: object
    next_review_date: date


@dataclass
class _CompletedRow:
    activity_id: object


class _DummyCountResult:
    def __init__(self, value: int):
        self._value = value

    def scalar(self):
        return self._value


class _DummyScalars:
    def __init__(self, rows: list):
        self._rows = rows

    def all(self):
        return self._rows


class _DummyActivitiesResult:
    def __init__(self, rows: list):
        self._rows = rows

    def scalars(self):
        return _DummyScalars(self._rows)


class _DummyIterableResult:
    def __init__(self, rows: list):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


class _DummySession:
    def __init__(self, responses: list):
        self._responses = responses
        self._statements = []
        self._index = 0

    async def execute(self, stmt):
        self._statements.append(stmt)
        response = self._responses[self._index]
        self._index += 1
        return response


class TestActivityTimelineReviewStatus:
    @pytest.mark.asyncio
    async def test_timeline_marks_completed_today_and_keeps_next_review_date(self):
        """`review_completed_today` and `next_review_date` should coexist."""
        activity_id = uuid4()
        fake_user = type("FakeUser", (), {"id": uuid4()})()
        now_utc = datetime(2026, 2, 20, 12, 30, tzinfo=timezone.utc)
        next_review_date = date(2026, 2, 23)

        activity = _FakeActivity(
            id=activity_id,
            title="Python 语法",
            summary="控制流与循环",
            activity_type="学习新知识",
            subject_name="Python",
            related_node_labels=["控制流", "循环结构"],
            message_count=8,
            study_depth="中等理解",
            source="conversation",
            activity_date=now_utc.date(),
            activity_time=now_utc,
        )

        db = _DummySession(
            responses=[
                _DummyCountResult(1),
                _DummyActivitiesResult([activity]),
                _DummyIterableResult(
                    [_NextReviewRow(activity_id, next_review_date)]
                ),
                _DummyIterableResult([_CompletedRow(activity_id)]),
            ]
        )

        result = await get_activity_timeline(
            user=fake_user,
            db=db,
            page=1,
            limit=20,
            space_id=None,
            activity_type=None,
        )

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].next_review_date == next_review_date
        assert result.items[0].review_completed_today is True

    @pytest.mark.asyncio
    async def test_timeline_defaults_review_completed_today_false(self):
        """`review_completed_today` should be false when no completed row exists."""
        activity_id = uuid4()
        fake_user = type("FakeUser", (), {"id": uuid4()})()
        now_utc = datetime(2026, 2, 20, 13, 0, tzinfo=timezone.utc)

        activity = _FakeActivity(
            id=activity_id,
            title="数据库迁移",
            summary="迁移脚本与回滚",
            activity_type="探讨",
            subject_name="数据库",
            related_node_labels=["迁移", "回滚"],
            message_count=6,
            study_depth="中等理解",
            source="conversation",
            activity_date=now_utc.date(),
            activity_time=now_utc,
        )

        db = _DummySession(
            responses=[
                _DummyCountResult(1),
                _DummyActivitiesResult([activity]),
                _DummyIterableResult([]),
                _DummyIterableResult([]),
            ]
        )

        result = await get_activity_timeline(
            user=fake_user,
            db=db,
            page=1,
            limit=20,
            space_id=None,
            activity_type=None,
        )

        assert len(result.items) == 1
        assert result.items[0].review_completed_today is False

    @pytest.mark.asyncio
    async def test_timeline_completed_window_uses_server_timezone_day_boundary(
        self, monkeypatch
    ):
        """`completed_at` filter should use [start_utc, end_utc) of server-local day."""

        class _FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                local_now = cls(
                    2026,
                    2,
                    20,
                    23,
                    30,
                    tzinfo=timezone(timedelta(hours=8)),
                )
                if tz is None:
                    return local_now
                return local_now.astimezone(tz)

        monkeypatch.setattr(activity_router_module, "datetime", _FrozenDateTime)

        activity_id = uuid4()
        fake_user = type("FakeUser", (), {"id": uuid4()})()
        now_utc = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
        activity = _FakeActivity(
            id=activity_id,
            title="系统设计",
            summary="缓存策略",
            activity_type="探讨",
            subject_name="后端",
            related_node_labels=["缓存", "一致性"],
            message_count=5,
            study_depth="中等理解",
            source="conversation",
            activity_date=now_utc.date(),
            activity_time=now_utc,
        )

        db = _DummySession(
            responses=[
                _DummyCountResult(1),
                _DummyActivitiesResult([activity]),
                _DummyIterableResult([]),
                _DummyIterableResult([]),
            ]
        )

        await get_activity_timeline(
            user=fake_user,
            db=db,
            page=1,
            limit=20,
            space_id=None,
            activity_type=None,
        )

        completed_stmt = db._statements[3]
        completed_where = list(completed_stmt._where_criteria)
        completed_at_bounds = [
            criterion.right.value
            for criterion in completed_where
            if getattr(getattr(criterion, "left", None), "name", None)
            == "completed_at"
        ]
        status_values = [
            criterion.right.value
            for criterion in completed_where
            if getattr(getattr(criterion, "left", None), "name", None) == "status"
        ]
        user_values = [
            criterion.right.value
            for criterion in completed_where
            if getattr(getattr(criterion, "left", None), "name", None) == "user_id"
        ]

        expected_start_utc = datetime(2026, 2, 19, 16, 0, tzinfo=timezone.utc)
        expected_end_utc = datetime(2026, 2, 20, 16, 0, tzinfo=timezone.utc)

        assert expected_start_utc in completed_at_bounds
        assert expected_end_utc in completed_at_bounds
        assert status_values == ["completed"]
        assert user_values == [fake_user.id]
