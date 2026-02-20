"""Review due count behavior tests."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from auth.dependencies import get_current_user
from review import router as review_router_module
from review.router import router
from review.service import get_due_reviews_by_space, get_due_reviews_total


@dataclass
class _FakeReview:
    id: object
    activity_id: object
    review_number: int
    scheduled_date: object
    node_label: str | None = None
    study_depth: str | None = None


@dataclass
class _FakeActivity:
    title: str
    related_node_labels: list[str] | None = None


class _DummyResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _DummySession:
    def __init__(self, value: int, captured: dict):
        self._value = value
        self._captured = captured

    async def execute(self, stmt):
        self._captured["stmt"] = stmt
        return _DummyResult(self._value)


class _DummySessionContext:
    def __init__(self, value: int, captured: dict):
        self._session = _DummySession(value=value, captured=captured)

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _DummyScalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _DummyRowsResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _DummyScalars(self._rows)

    def all(self):
        return self._rows


class _DummyRowsSession:
    def __init__(self, rows: list, captured: dict):
        self._rows = rows
        self._captured = captured

    async def execute(self, stmt):
        self._captured["stmt"] = stmt
        return _DummyRowsResult(self._rows)


class _DummyRowsSessionContext:
    def __init__(self, rows: list, captured: dict):
        self._session = _DummyRowsSession(rows=rows, captured=captured)

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class TestDueReviewTotals:
    """Tests for due-review total semantics."""

    @pytest.mark.asyncio
    async def test_get_due_reviews_total_uses_pending_and_due_date_filters(
        self, monkeypatch
    ):
        """Service query should use DISTINCT activity_id + pending + scheduled_date<=today."""
        captured = {}
        expected_total = 7
        user_id = uuid4()

        monkeypatch.setattr(
            "review.service.get_scoped_session",
            lambda: _DummySessionContext(value=expected_total, captured=captured),
        )

        total = await get_due_reviews_total(user_id)
        assert total == expected_total

        stmt = captured["stmt"]
        stmt_sql = str(stmt).lower().replace(" ", "")
        assert "count(distinct(review_schedules.activity_id))" in stmt_sql

        where_sql = " ".join(str(c) for c in stmt._where_criteria)
        assert "review_schedules.user_id" in where_sql
        assert "review_schedules.status" in where_sql
        assert "review_schedules.scheduled_date" in where_sql
        assert "<=" in where_sql

        criteria = {c.left.name: c for c in stmt._where_criteria}
        assert criteria["user_id"].right.value == user_id
        assert criteria["status"].right.value == "pending"
        assert criteria["scheduled_date"].right.value == datetime.now(
            timezone.utc
        ).date()

    @pytest.mark.asyncio
    async def test_due_endpoint_total_is_not_limited_by_items_limit(self, monkeypatch):
        """`items` should obey limit, while `total` returns deduped event count."""
        fake_user = type("FakeUser", (), {"id": uuid4()})()
        today = datetime.now(timezone.utc).date()

        async def mock_get_current_user():
            return fake_user

        async def mock_get_due_reviews(user_id, limit):
            assert user_id == fake_user.id
            assert limit == 1
            return [
                _FakeReview(
                    id=uuid4(),
                    activity_id=uuid4(),
                    review_number=1,
                    scheduled_date=today,
                    study_depth="中等理解",
                )
            ]

        async def mock_get_due_reviews_total(user_id):
            assert user_id == fake_user.id
            return 2

        monkeypatch.setattr(
            review_router_module, "get_due_reviews", mock_get_due_reviews
        )
        monkeypatch.setattr(
            review_router_module, "get_due_reviews_total", mock_get_due_reviews_total
        )

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = mock_get_current_user

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/review/due", params={"limit": 1})

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_get_due_reviews_by_space_uses_space_filter_and_activity_dedup(
        self, monkeypatch
    ):
        """Space query should filter by space_id and dedupe by activity_id."""
        captured = {}
        user_id = uuid4()
        space_id = uuid4()

        monkeypatch.setattr(
            "review.service.get_scoped_session",
            lambda: _DummyRowsSessionContext(rows=[], captured=captured),
        )

        rows = await get_due_reviews_by_space(user_id, space_id, limit=10)
        assert rows == []

        stmt_sql = str(captured["stmt"]).lower().replace(" ", "")
        assert "row_number()over(partitionbyreview_schedules.activity_id" in stmt_sql
        assert "study_activity_logs.space_id" in stmt_sql
        assert "review_schedules.status" in stmt_sql
        assert "review_schedules.scheduled_date<=" in stmt_sql

    @pytest.mark.asyncio
    async def test_get_due_reviews_by_space_returns_rows(self, monkeypatch):
        """Space query should return (review, activity) tuples."""
        today = datetime.now(timezone.utc).date()
        fake_review = _FakeReview(
            id=uuid4(),
            activity_id=uuid4(),
            review_number=1,
            scheduled_date=today,
            study_depth="中等理解",
        )
        fake_activity = _FakeActivity(
            title="数据库索引原理",
            related_node_labels=["数据库索引"],
        )
        captured = {}

        monkeypatch.setattr(
            "review.service.get_scoped_session",
            lambda: _DummyRowsSessionContext(
                rows=[(fake_review, fake_activity)], captured=captured
            ),
        )

        rows = await get_due_reviews_by_space(uuid4(), uuid4(), limit=10)
        assert len(rows) == 1
        r, a = rows[0]
        assert r.review_number == 1
        assert a.title == "数据库索引原理"
