"""Tests for due-review context selection in activity suggestions."""

from dataclasses import dataclass
from datetime import date
from uuid import uuid4

import pytest

from activity.suggestion import _fetch_due_reviews


@dataclass
class _FakeReview:
    id: object
    activity_id: object
    node_label: str
    review_number: int
    scheduled_date: date
    study_depth: str | None = None


class _DummyResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _DummySession:
    def __init__(self, rows):
        self._rows = rows
        self.stmt = None

    async def execute(self, stmt):
        self.stmt = stmt
        return _DummyResult(self._rows)


class TestSuggestionDueReviews:
    @pytest.mark.asyncio
    async def test_fetch_due_reviews_uses_activity_dedup_query(self):
        """Query should dedupe due reviews by activity_id with row_number window."""
        session = _DummySession(rows=[])

        result = await _fetch_due_reviews(uuid4(), session)

        assert result == []
        stmt_sql = str(session.stmt).lower().replace(" ", "")
        assert "row_number()over(partitionbyreview_schedules.activity_id" in stmt_sql
        assert "review_schedules.user_id" in stmt_sql
        assert "review_schedules.status" in stmt_sql
        assert "review_schedules.scheduled_date<=" in stmt_sql

    @pytest.mark.asyncio
    async def test_fetch_due_reviews_returns_review_and_preferences_rows(self):
        """Function should return `(ReviewSchedule, learning_preferences)` tuples."""
        fake_review = _FakeReview(
            id=uuid4(),
            activity_id=uuid4(),
            node_label="Python 控制流",
            review_number=1,
            scheduled_date=date.today(),
            study_depth="中等理解",
        )
        rows = [(fake_review, {"preset_preferences": ["solid"]})]
        session = _DummySession(rows=rows)

        result = await _fetch_due_reviews(uuid4(), session)

        assert len(result) == 1
        review, prefs = result[0]
        assert review.node_label == "Python 控制流"
        assert review.review_number == 1
        assert prefs == {"preset_preferences": ["solid"]}
