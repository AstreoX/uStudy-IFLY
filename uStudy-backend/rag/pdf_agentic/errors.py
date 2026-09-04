"""Stable, user-safe errors for the Agentic PDF visual index pipeline."""

from __future__ import annotations

from enum import StrEnum


class PdfVisualIndexErrorCode(StrEnum):
    """Machine-readable failure codes persisted by the orchestration layer."""

    NOT_FOUND = "pdf_not_found"
    OPEN_FAILED = "pdf_open_failed"
    ENCRYPTED = "pdf_encrypted"
    EMPTY = "pdf_empty"
    PAGE_LIMIT_EXCEEDED = "pdf_page_limit_exceeded"
    INVALID_PAGE_SIZE = "pdf_invalid_page_size"
    PAGE_RENDER_FAILED = "pdf_page_render_failed"
    IMAGE_LIMIT_EXCEEDED = "pdf_image_limit_exceeded"
    DERIVED_SIZE_EXCEEDED = "pdf_derived_size_exceeded"
    INSUFFICIENT_DISK = "pdf_insufficient_disk"
    MANIFEST_INVALID = "pdf_manifest_invalid"
    CANCELLED = "pdf_processing_cancelled"
    STORAGE_FAILED = "pdf_storage_failed"


class PdfVisualIndexError(RuntimeError):
    """An expected PDF indexing failure with a stable public error code."""

    def __init__(
        self,
        error_code: PdfVisualIndexErrorCode | str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.error_code = str(error_code)
        self.retryable = retryable


class TocModelResponseError(ValueError):
    """Raised when a VLM response does not match the strict TOC JSON contract."""
