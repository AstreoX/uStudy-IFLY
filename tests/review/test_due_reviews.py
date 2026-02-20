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
from review.service import get_due_reviews_total


@dataclass
class _FakeReview:
    id: object
    activity_id: object
    node_label: str
    review_number: int
    scheduled_date: object
    study_depth: str | None = None


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
                    node_label="Python 控制流",
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
