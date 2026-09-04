from uuid import uuid4

from chat.rag_auto_inject import (
    filter_auto_rag_results,
    has_explicit_document_search_intent,
    should_skip_auto_rag,
)
from rag.retrieval.base import SearchResult


def _result(
    *,
    score: float,
    retrieval_score: float | None,
    retrieval_source: str,
    rerank_score: float | None = None,
) -> SearchResult:
    return SearchResult(
        chunk_id=uuid4(),
        document_id=uuid4(),
        content="content",
        score=score,
        metadata={},
        document_title="doc",
        document_filename=None,
        retrieval_score=retrieval_score,
        rerank_score=rerank_score,
        retrieval_source=retrieval_source,
    )


def test_should_skip_auto_rag_for_generic_follow_up():
    assert should_skip_auto_rag("我需要详细解释")
    assert should_skip_auto_rag("图在哪里？")
    assert should_skip_auto_rag("继续")


def test_should_not_skip_auto_rag_when_document_intent_is_explicit():
    query = "根据我上传的文档详细解释这张 wireshark 抓包图"
    assert has_explicit_document_search_intent(query)
    assert not should_skip_auto_rag(query)


def test_filter_auto_rag_results_drops_low_score_results():
    high = _result(score=0.8, retrieval_score=0.8, retrieval_source="text")
    low = _result(score=0.3, retrieval_score=0.3, retrieval_source="text")

    filtered = filter_auto_rag_results(
        [high, low],
        score_threshold=0.5,
    )

    assert filtered == [high]


def test_filter_auto_rag_results_respects_max_results():
    results = [
        _result(score=0.9, retrieval_score=0.9, retrieval_source="text"),
        _result(score=0.8, retrieval_score=0.8, retrieval_source="text"),
        _result(score=0.7, retrieval_score=0.7, retrieval_source="text"),
        _result(score=0.6, retrieval_score=0.6, retrieval_source="text"),
    ]

    filtered = filter_auto_rag_results(results, score_threshold=0.0, max_results=3)

    assert len(filtered) == 3
