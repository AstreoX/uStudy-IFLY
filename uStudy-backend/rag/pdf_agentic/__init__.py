"""Agentic visual indexing primitives for large and scanned PDF documents."""

from .agent import TocIndexAgent
from .errors import (
    PdfVisualIndexError,
    PdfVisualIndexErrorCode,
    TocModelResponseError,
)
from .models import (
    NativePageText,
    NumericPageAnchor,
    OutlineEntry,
    PageAssetManifest,
    PdfPreflight,
    RenderManifest,
    TocAgentResult,
    TocLocateDecision,
    TocPageExtraction,
)
from .outline import (
    compute_page_offset,
    merge_outline_entries,
    parse_anchor_response,
    parse_model_json,
    parse_toc_locate_response,
    parse_toc_page_response,
    render_outline_markdown,
    resolve_outline_entries,
    sanitize_title,
    write_outline_artifacts,
)
from .renderer import (
    expected_asset_count,
    iter_native_page_text,
    load_render_manifest,
    preflight_pdf,
    render_pdf_visual_index,
)

__all__ = [
    "NativePageText",
    "NumericPageAnchor",
    "OutlineEntry",
    "PageAssetManifest",
    "PdfPreflight",
    "PdfVisualIndexError",
    "PdfVisualIndexErrorCode",
    "RenderManifest",
    "TocAgentResult",
    "TocIndexAgent",
    "TocLocateDecision",
    "TocModelResponseError",
    "TocPageExtraction",
    "compute_page_offset",
    "expected_asset_count",
    "iter_native_page_text",
    "load_render_manifest",
    "merge_outline_entries",
    "parse_anchor_response",
    "parse_model_json",
    "parse_toc_locate_response",
    "parse_toc_page_response",
    "preflight_pdf",
    "render_outline_markdown",
    "render_pdf_visual_index",
    "resolve_outline_entries",
    "sanitize_title",
    "write_outline_artifacts",
]
