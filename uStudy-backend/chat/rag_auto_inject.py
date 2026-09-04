"""Helpers for automatic RAG injection safeguards."""

from __future__ import annotations

import re

from rag.retrieval.base import SearchResult

_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_PUNCT_RE = re.compile(r"[？?！!。．…,.，、:：;；]+$")

# Generic follow-up prompts tend to be answered from the current multimodal
# context, not from the knowledge base. Auto-injecting citations for them
# creates obvious false positives.
_GENERIC_QUERY_PATTERNS = (
    re.compile(r"^(继续|展开(讲讲|说明)?|再解释一下|详细(解释|讲解|说明)|我需要详细解释)$"),
    re.compile(r"^(帮我|给我|请)?(详细|具体)?(解释|讲解|说明)(一下|一遍)?$"),
    re.compile(r"^(图|图片|这张图|这个图)(在哪里|在哪|怎么看|是什么意思)$"),
)

_EXPLICIT_DOCUMENT_INTENT_KEYWORDS = (
    "文档",
    "资料",
    "知识库",
    "笔记",
    "上传",
    "来源",
    "参考",
    "note",
    "notes",
    "doc",
    "docs",
    "document",
    "documents",
    "source",
    "reference",
    "upload",
    "uploaded",
)


def normalize_auto_rag_query(query: str) -> str:
    """Normalize a query for lightweight intent heuristics."""
    normalized = _WHITESPACE_RE.sub("", (query or "").strip()).lower()
    return _TRAILING_PUNCT_RE.sub("", normalized)


def has_explicit_document_search_intent(query: str) -> bool:
    """Return True when the user explicitly asks to use uploaded knowledge."""
    normalized = normalize_auto_rag_query(query)
    return any(keyword in normalized for keyword in _EXPLICIT_DOCUMENT_INTENT_KEYWORDS)


def should_skip_auto_rag(query: str) -> bool:
    """Skip auto RAG when the query is too generic to retrieve against safely."""
    normalized = normalize_auto_rag_query(query)
    if not normalized:
        return True
    if has_explicit_document_search_intent(normalized):
        return False
    return any(pattern.match(normalized) for pattern in _GENERIC_QUERY_PATTERNS)


def filter_auto_rag_results(
    results: list[SearchResult],
    *,
    score_threshold: float = 0.0,
    max_results: int = 3,
) -> list[SearchResult]:
    """Filter auto-injected results by score threshold and cap at max_results."""
    filtered = [r for r in results if r.score >= score_threshold]
    return filtered[:max_results]
