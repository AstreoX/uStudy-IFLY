"""Dependency-free value objects shared by Agentic PDF components."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class PdfPreflight:
    """Validated metadata obtained by opening a PDF from its filesystem path."""

    pdf_path: Path
    page_count: int


@dataclass(frozen=True, slots=True)
class PageAssetManifest:
    """One immutable rendered page asset."""

    pages_per_image: Literal[1, 2, 4]
    physical_page_start: int
    physical_page_end: int
    relative_path: str
    mime_type: str
    width: int
    height: int
    byte_size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RenderManifest:
    """Complete output of one streaming render pass."""

    schema_version: int
    page_count: int
    render_dpi: int
    render_max_pixels: int
    webp_quality: int
    max_image_bytes: int
    lod_max_side: int
    native_text_jsonl: str
    native_text_page_count: int
    native_text_nonempty_page_count: int
    assets: tuple[PageAssetManifest, ...]
    derived_bytes: int
    manifest_path: str = "manifest.json"

    @property
    def asset_count(self) -> int:
        return len(self.assets)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["asset_count"] = self.asset_count
        result["assets"] = [asset.to_dict() for asset in self.assets]
        return result

    def find_asset(
        self, pages_per_image: int, physical_page: int
    ) -> PageAssetManifest | None:
        """Return the aligned asset containing a 1-based physical page."""

        if pages_per_image not in (1, 2, 4) or physical_page < 1:
            return None
        start = ((physical_page - 1) // pages_per_image) * pages_per_image + 1
        for asset in self.assets:
            if (
                asset.pages_per_image == pages_per_image
                and asset.physical_page_start == start
            ):
                return asset
        return None


@dataclass(frozen=True, slots=True)
class NativePageText:
    """One line in the native-text JSONL checkpoint."""

    physical_page: int
    text: str


@dataclass(frozen=True, slots=True)
class OutlineEntry:
    """One flattened, preorder table-of-contents entry."""

    title: str
    level: int
    printed_page_label: str | None
    printed_page_number: int | None
    source_physical_page: int | None = None
    resolved_pdf_page: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class NumericPageAnchor:
    """Visual evidence linking a printed page number to a physical PDF page."""

    printed_page_number: int
    physical_pdf_page: int


@dataclass(frozen=True, slots=True)
class TocPageExtraction:
    """Strict extraction result for one physical TOC page."""

    physical_page: int
    entries: tuple[OutlineEntry, ...]
    continues: bool


@dataclass(frozen=True, slots=True)
class TocLocateDecision:
    """A single action emitted by the coarse TOC locator."""

    status: Literal["found", "continue", "not_found"]
    toc_start: int | None = None
    toc_end: int | None = None
    requests: tuple[tuple[int, Literal[1, 2, 4]], ...] = ()


@dataclass(frozen=True, slots=True)
class TocAgentResult:
    """Degraded-success-aware result consumed by the durable orchestrator."""

    status: Literal["ready", "not_found", "failed"]
    entries: tuple[OutlineEntry, ...] = ()
    anchors: tuple[NumericPageAnchor, ...] = ()
    page_offset: int | None = None
    toc_physical_page_start: int | None = None
    toc_physical_page_end: int | None = None
    call_keys: tuple[str, ...] = ()
    error_code: str | None = None
    error_detail: str | None = field(default=None, repr=False)
