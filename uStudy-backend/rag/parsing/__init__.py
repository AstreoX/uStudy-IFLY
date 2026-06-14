"""Parsing utilities for format resolution and document normalization."""

from rag.parsing.formats import (
    DocumentFormatError,
    LegacyDocumentNormalizationError,
    NormalizedDocument,
    ResolvedDocumentFormat,
    canonical_type_from_hint,
    find_office_binary,
    get_canonical_mime,
    get_supported_document_extensions,
    get_supported_document_mime_types,
    normalize_legacy_document,
    resolve_document_format,
)

__all__ = [
    "DocumentFormatError",
    "LegacyDocumentNormalizationError",
    "NormalizedDocument",
    "ResolvedDocumentFormat",
    "canonical_type_from_hint",
    "find_office_binary",
    "get_canonical_mime",
    "get_supported_document_extensions",
    "get_supported_document_mime_types",
    "normalize_legacy_document",
    "resolve_document_format",
]
