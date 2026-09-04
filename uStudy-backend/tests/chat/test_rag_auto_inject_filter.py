"""Tests for updated filter_auto_rag_results."""
import uuid
from rag.retrieval.base import SearchResult
from chat.rag_auto_inject import filter_auto_rag_results


def _make_result(score: float, source: str = "text") -> SearchResult:
    return SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content="test content",
        score=score,
        metadata={},
        document_title="Doc",
        document_filename="doc.pdf",
        retrieval_score=score,
        retrieval_source=source,
    )


def test_filter_removes_below_threshold():
    results = [_make_result(0.8), _make_result(0.3), _make_result(0.1)]
    filtered = filter_auto_rag_results(results, score_threshold=0.5)
    assert len(filtered) == 1
    assert filtered[0].score == 0.8


def test_filter_respects_max_results():
    results = [_make_result(0.9), _make_result(0.8), _make_result(0.7), _make_result(0.6)]
    filtered = filter_auto_rag_results(results, score_threshold=0.0, max_results=3)
    assert len(filtered) == 3


def test_filter_empty_input_returns_empty():
    assert filter_auto_rag_results([], score_threshold=0.5) == []
