"""Tests for timeline review status tags."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

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
class _NextPendingRow:
    activity_id: object
    scheduled_date: date
    review_number: int


@dataclass
class _LastCompletedRow:
    activity_id: object
    completed_at: datetime
    review_number: int


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
    async def test_timeline_shows_both_completed_and_next_pending(self):
        """Both last_completed and next_pending fields should coexist."""
        activity_id = uuid4()
        fake_user = type("FakeUser", (), {"id": uuid4()})()
        now_utc = datetime(2026, 2, 20, 12, 30, tzinfo=timezone.utc)
        next_review_date = date(2026, 2, 23)
        completed_at = datetime(2026, 2, 21, 14, 30, tzinfo=timezone.utc)

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
                    [_NextPendingRow(activity_id, next_review_date, 2)]
                ),
                _DummyIterableResult(
                    [_LastCompletedRow(activity_id, completed_at, 1)]
                ),
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
        item = result.items[0]
        assert item.next_review_date == next_review_date
        assert item.next_review_number == 2
        assert item.last_completed_review_number == 1
        assert item.last_completed_at == completed_at

    @pytest.mark.asyncio
    async def test_timeline_defaults_to_none_when_no_reviews(self):
        """All review fields should be None when no review records exist."""
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
        item = result.items[0]
        assert item.next_review_date is None
        assert item.next_review_number is None
        assert item.last_completed_review_number is None
        assert item.last_completed_at is None

    @pytest.mark.asyncio
    async def test_timeline_window_function_picks_latest_completed(self):
        """The last_completed fields should reflect the most recent completed review."""
        activity_id = uuid4()
        fake_user = type("FakeUser", (), {"id": uuid4()})()
        now_utc = datetime(2026, 2, 27, 9, 15, tzinfo=timezone.utc)

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

        # Simulate window function already returning only the top-1 row
        latest_completed_at = datetime(2026, 2, 27, 9, 15, tzinfo=timezone.utc)
        next_review_date = date(2026, 3, 6)

        db = _DummySession(
            responses=[
                _DummyCountResult(1),
                _DummyActivitiesResult([activity]),
                _DummyIterableResult(
                    [_NextPendingRow(activity_id, next_review_date, 4)]
                ),
                _DummyIterableResult(
                    [_LastCompletedRow(activity_id, latest_completed_at, 3)]
                ),
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

        item = result.items[0]
        assert item.last_completed_review_number == 3
        assert item.last_completed_at == latest_completed_at
        assert item.next_review_number == 4
        assert item.next_review_date == next_review_date
