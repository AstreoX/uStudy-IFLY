"""Optional Haystack integration helpers.

The project keeps its existing application tables as the source of truth.
When Haystack dependencies are installed, chunks are additionally mirrored into
Haystack's pgvector table to enable gradual migration of retrieval quality.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Iterable

from config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def haystack_available() -> bool:
    """Return whether the optional Haystack integration is importable."""
    try:
        import haystack  # noqa: F401
        import haystack_integrations  # noqa: F401
    except ImportError:
        return False
    return True


def to_sync_postgres_dsn(async_database_url: str) -> str:
    """Convert SQLAlchemy async URLs into sync PostgreSQL DSNs for Haystack."""
    if async_database_url.startswith("postgresql+asyncpg://"):
        return async_database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if async_database_url.startswith("postgresql+psycopg://"):
        return async_database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    return async_database_url


def get_haystack_document_store() -> Any | None:
    """Create a PgvectorDocumentStore instance when Haystack is available."""
    settings = get_settings()
    if not settings.haystack_mirror_enabled or not haystack_available():
        return None

    from haystack_integrations.document_stores.pgvector import PgvectorDocumentStore

    common_kwargs = {
        "connection_string": to_sync_postgres_dsn(settings.database_url),
        "create_extension": False,
        "embedding_dimension": settings.embedding_dimension,
        "vector_function": "cosine_similarity",
        "recreate_table": False,
    }
    extended_kwargs = {
        **common_kwargs,
        "schema_name": settings.haystack_schema_name,
        "table_name": settings.haystack_table_name,
        "language": settings.haystack_keyword_language,
        "vector_type": settings.haystack_vector_type,
        "search_strategy": settings.haystack_search_strategy,
        "hnsw_index_name": settings.haystack_hnsw_index_name,
        "keyword_index_name": settings.haystack_keyword_index_name,
    }
    try:
        return PgvectorDocumentStore(**extended_kwargs)
    except TypeError:
        logger.warning("PgvectorDocumentStore constructor rejected extended kwargs, retrying with minimal config")
        return PgvectorDocumentStore(**common_kwargs)


def make_space_filter(space_id: str) -> dict[str, Any]:
    """Build a Haystack-compatible metadata filter for a space."""
    return {"field": "meta.space_id", "operator": "==", "value": str(space_id)}


def document_to_meta(document: Any) -> dict[str, Any]:
    """Extract a plain metadata dict from a Haystack document-like object."""
    meta = getattr(document, "meta", None) or {}
    if isinstance(meta, dict):
        return meta
    try:
        return dict(meta)
    except Exception:
        logger.warning("Unable to coerce Haystack metadata to dict: %r", meta)
        return {}


def mirror_chunk_rows(rows: Iterable[dict[str, Any]]) -> None:
    """Mirror app chunk rows into the optional Haystack document store."""
    store = get_haystack_document_store()
    if store is None:
        return

    from haystack import Document
    from haystack.document_stores import DuplicatePolicy

    documents = [
        Document(
            id=str(row["id"]),
            content=row["content"],
            embedding=row["embedding_vector"],
            meta=dict(row["meta"]),
        )
        for row in rows
    ]
    if not documents:
        return
    store.write_documents(documents=documents, policy=DuplicatePolicy.OVERWRITE)


def delete_mirror_documents(document_ids: Iterable[str]) -> None:
    """Delete mirrored documents from Haystack if the mirror is enabled."""
    store = get_haystack_document_store()
    if store is None:
        return

    ids = [str(doc_id) for doc_id in document_ids if str(doc_id).strip()]
    if not ids:
        return

    try:
        store.delete_documents(document_ids=ids)
    except TypeError:
        # Older integrations used positional args.
        store.delete_documents(ids)
