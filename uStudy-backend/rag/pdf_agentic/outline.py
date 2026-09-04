"""Strict TOC schemas, page-offset inference, and deterministic artifacts."""

from __future__ import annotations

import html
import json
import os
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from .errors import TocModelResponseError
from .models import (
    NumericPageAnchor,
    OutlineEntry,
    TocLocateDecision,
    TocPageExtraction,
)

_CODE_FENCE = re.compile(
    r"\A```(?:json)?[ \t]*\r?\n?(.*?)\r?\n?```\s*\Z",
    flags=re.IGNORECASE | re.DOTALL,
)
_MARKDOWN_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+.!|>~-])")


def _reject_nonstandard_json(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def parse_model_json(raw: str) -> dict[str, Any]:
    """Parse a JSON object, allowing only a surrounding `````json```` fence."""

    if not isinstance(raw, str) or not raw.strip():
        raise TocModelResponseError("VLM response is empty")
    cleaned = raw.strip().lstrip("\ufeff")
    if cleaned.startswith("```"):
        match = _CODE_FENCE.fullmatch(cleaned)
        if match is None:
            raise TocModelResponseError("VLM response has an invalid code fence")
        cleaned = match.group(1).strip()
    try:
        value = json.loads(cleaned, parse_constant=_reject_nonstandard_json)
    except (json.JSONDecodeError, ValueError) as exc:
        raise TocModelResponseError("VLM response is not valid JSON") from exc
    if not isinstance(value, dict):
        raise TocModelResponseError("VLM response must be a JSON object")
    return value


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _optional_positive_int(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if not _is_int(value) or value < 1:
        raise TocModelResponseError(f"{field_name} must be a positive integer or null")
    return value


def _clean_inline(value: str, *, max_length: int) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    without_controls = "".join(
        " " if char in "\r\n\t" else char
        for char in normalized
        if not unicodedata.category(char).startswith("C") or char in "\r\n\t"
    )
    collapsed = " ".join(without_controls.split()).strip()
    collapsed = collapsed[:max_length].rstrip()
    escaped_html = html.escape(collapsed, quote=False)
    return _MARKDOWN_SPECIAL.sub(r"\\\1", escaped_html)


def sanitize_title(title: str, *, max_length: int = 500) -> str:
    """Remove controls and escape HTML/Markdown from an untrusted TOC title."""

    if not isinstance(title, str):
        raise TypeError("title must be a string")
    if max_length < 1:
        raise ValueError("max_length must be positive")
    return _clean_inline(title, max_length=max_length)


def _sanitize_page_label(label: str) -> str:
    return _clean_inline(label, max_length=64)


def parse_toc_locate_response(raw: str) -> TocLocateDecision:
    """Validate one action from the coarse 4/2/1-up locator loop."""

    value = parse_model_json(raw)
    status = value.get("status")
    if status not in {"found", "continue", "not_found"}:
        raise TocModelResponseError(
            "locator status must be found, continue, or not_found"
        )

    toc_start = _optional_positive_int(value.get("toc_start"), "toc_start")
    toc_end = _optional_positive_int(value.get("toc_end"), "toc_end")
    requests_value = value.get("requests", [])
    if not isinstance(requests_value, list) or len(requests_value) > 4:
        raise TocModelResponseError("requests must be an array of at most four items")
    requests: list[tuple[int, Any]] = []
    for request in requests_value:
        if not isinstance(request, dict):
            raise TocModelResponseError("each locator request must be an object")
        physical_page = request.get("physical_page")
        pages_per_image = request.get("pages_per_image")
        if not _is_int(physical_page) or physical_page < 1:
            raise TocModelResponseError("request physical_page must be positive")
        if pages_per_image not in (1, 2, 4):
            raise TocModelResponseError("request pages_per_image must be 1, 2, or 4")
        requests.append((physical_page, pages_per_image))

    if status == "found":
        if toc_start is None:
            raise TocModelResponseError("found response requires toc_start")
        if toc_end is not None and toc_end < toc_start:
            raise TocModelResponseError("toc_end cannot precede toc_start")
    elif toc_start is not None or toc_end is not None:
        raise TocModelResponseError("only found responses may contain a TOC range")

    return TocLocateDecision(
        status=status,
        toc_start=toc_start,
        toc_end=toc_end,
        requests=tuple(requests),
    )


def parse_toc_page_response(raw: str, physical_page: int) -> TocPageExtraction:
    """Validate and sanitize one physical TOC page extraction."""

    if physical_page < 1:
        raise ValueError("physical_page must be positive")
    value = parse_model_json(raw)
    entries_value = value.get("entries")
    continues = value.get("continues")
    if not isinstance(entries_value, list):
        raise TocModelResponseError("entries must be an array")
    if not isinstance(continues, bool):
        raise TocModelResponseError("continues must be a boolean")

    entries: list[OutlineEntry] = []
    for item in entries_value:
        if not isinstance(item, dict):
            raise TocModelResponseError("each TOC entry must be an object")
        raw_title = item.get("title")
        if not isinstance(raw_title, str):
            raise TocModelResponseError("entry title must be a string")
        title = sanitize_title(raw_title)
        if not title:
            raise TocModelResponseError("entry title cannot be empty")

        level = item.get("level")
        if not _is_int(level) or not 1 <= level <= 20:
            raise TocModelResponseError("entry level must be an integer from 1 to 20")

        raw_label = item.get("printed_page_label")
        if raw_label is not None and not isinstance(raw_label, str):
            raise TocModelResponseError("printed_page_label must be a string or null")
        label = _sanitize_page_label(raw_label) if raw_label is not None else None
        if label == "":
            label = None
        number = _optional_positive_int(
            item.get("printed_page_number"), "printed_page_number"
        )
        if number is None and raw_label is not None and raw_label.strip().isdigit():
            parsed_number = int(raw_label.strip())
            number = parsed_number if parsed_number > 0 else None
        if label is None and number is not None:
            label = str(number)
        if (
            raw_label is not None
            and raw_label.strip().isdigit()
            and number is not None
            and int(raw_label.strip()) != number
        ):
            raise TocModelResponseError(
                "numeric printed_page_label disagrees with printed_page_number"
            )

        entries.append(
            OutlineEntry(
                title=title,
                level=level,
                printed_page_label=label,
                printed_page_number=number,
                source_physical_page=physical_page,
            )
        )
    return TocPageExtraction(
        physical_page=physical_page,
        entries=tuple(entries),
        continues=continues,
    )


def parse_anchor_response(raw: str) -> tuple[NumericPageAnchor, ...]:
    """Validate numeric page anchors returned from post-TOC content pages."""

    value = parse_model_json(raw)
    anchors_value = value.get("anchors")
    if not isinstance(anchors_value, list):
        raise TocModelResponseError("anchors must be an array")
    anchors: list[NumericPageAnchor] = []
    seen: set[tuple[int, int]] = set()
    for item in anchors_value:
        if not isinstance(item, dict):
            raise TocModelResponseError("each anchor must be an object")
        printed = item.get("printed_page_number")
        physical = item.get("physical_pdf_page")
        if not _is_int(printed) or printed < 1:
            raise TocModelResponseError("anchor printed page must be positive")
        if not _is_int(physical) or physical < 1:
            raise TocModelResponseError("anchor physical page must be positive")
        key = (printed, physical)
        if key not in seen:
            anchors.append(
                NumericPageAnchor(
                    printed_page_number=printed,
                    physical_pdf_page=physical,
                )
            )
            seen.add(key)
    return tuple(anchors)


def merge_outline_entries(
    pages: Iterable[TocPageExtraction | Sequence[OutlineEntry]],
) -> tuple[OutlineEntry, ...]:
    """Deterministically flatten pages and remove boundary duplicates."""

    merged: list[OutlineEntry] = []
    seen: set[tuple[str, str]] = set()
    for page in pages:
        entries = page.entries if isinstance(page, TocPageExtraction) else page
        for entry in entries:
            page_identity = (
                str(entry.printed_page_number)
                if entry.printed_page_number is not None
                else (entry.printed_page_label or "").casefold()
            )
            key = (entry.title.casefold(), page_identity)
            if key in seen:
                continue
            seen.add(key)
            merged.append(entry)
    return tuple(merged)


def compute_page_offset(
    anchors: Iterable[NumericPageAnchor], *, page_count: int | None = None
) -> int | None:
    """Publish one offset only when at least two distinct anchors all agree."""

    if page_count is not None and page_count < 1:
        raise ValueError("page_count must be positive")
    unique = {
        (anchor.printed_page_number, anchor.physical_pdf_page) for anchor in anchors
    }
    if len(unique) < 2:
        return None
    if len({printed for printed, _ in unique}) < 2:
        return None
    offsets: set[int] = set()
    for printed, physical in unique:
        if printed < 1 or physical < 1:
            return None
        if page_count is not None and physical > page_count:
            return None
        offsets.add(physical - printed)
    if len(offsets) != 1:
        return None
    return offsets.pop()


def resolve_outline_entries(
    entries: Iterable[OutlineEntry],
    *,
    page_offset: int | None,
    page_count: int,
) -> tuple[OutlineEntry, ...]:
    """Apply a verified 1-based mapping, retaining null for unsafe targets."""

    if page_count < 1:
        raise ValueError("page_count must be positive")
    resolved: list[OutlineEntry] = []
    for entry in entries:
        target: int | None = None
        if page_offset is not None and entry.printed_page_number is not None:
            candidate = entry.printed_page_number + page_offset
            if 1 <= candidate <= page_count:
                target = candidate
        resolved.append(replace(entry, resolved_pdf_page=target))
    return tuple(resolved)


def render_outline_markdown(
    entries: Iterable[OutlineEntry],
    *,
    toc_physical_page_start: int | None,
    toc_physical_page_end: int | None,
    page_offset: int | None,
) -> str:
    """Generate deterministic Markdown; the VLM never authors this artifact."""

    if (toc_physical_page_start is None) != (toc_physical_page_end is None):
        raise ValueError("TOC range endpoints must both be set or both be null")
    if (
        toc_physical_page_start is not None
        and toc_physical_page_end is not None
        and (
            toc_physical_page_start < 1
            or toc_physical_page_end < toc_physical_page_start
        )
    ):
        raise ValueError("invalid TOC physical page range")

    toc_range = (
        "null"
        if toc_physical_page_start is None
        else f"{toc_physical_page_start}-{toc_physical_page_end}"
    )
    offset_value = "null" if page_offset is None else str(page_offset)
    printed_page_one = "null" if page_offset is None else str(page_offset + 1)
    lines = [
        "# Document outline",
        "",
        f"- TOC physical page range: `{toc_range}`",
        "- Mapping formula: `physical_pdf_page = printed_page_number + page_offset`",
        f"- page_offset: `{offset_value}`",
        f"- printed_page_1_pdf_page: `{printed_page_one}`",
        "",
        "## Entries",
        "",
    ]
    entry_count = 0
    for entry in entries:
        entry_count += 1
        indent = "  " * max(0, entry.level - 1)
        printed = entry.printed_page_label or "null"
        physical = (
            "null" if entry.resolved_pdf_page is None else str(entry.resolved_pdf_page)
        )
        lines.append(
            f"{indent}- {entry.title} — printed page `{printed}`; "
            f"PDF physical page `{physical}`"
        )
    if entry_count == 0:
        lines.append("_No table-of-contents entries were extracted._")
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.tmp")
    try:
        with temp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except OSError:
        temp.unlink(missing_ok=True)
        raise


def write_outline_artifacts(
    output_root: str | os.PathLike[str],
    entries: Iterable[OutlineEntry],
    *,
    toc_physical_page_start: int | None,
    toc_physical_page_end: int | None,
    page_offset: int | None,
) -> tuple[Path, Path]:
    """Atomically write deterministic ``outline.json`` and ``outline.md`` files."""

    root = Path(output_root).expanduser().resolve()
    materialized = tuple(entries)
    markdown = render_outline_markdown(
        materialized,
        toc_physical_page_start=toc_physical_page_start,
        toc_physical_page_end=toc_physical_page_end,
        page_offset=page_offset,
    )
    payload = {
        "schema_version": 1,
        "toc_physical_page_start": toc_physical_page_start,
        "toc_physical_page_end": toc_physical_page_end,
        "mapping_formula": "physical_pdf_page = printed_page_number + page_offset",
        "page_offset": page_offset,
        "printed_page_1_pdf_page": None if page_offset is None else page_offset + 1,
        "entries": [entry.to_dict() for entry in materialized],
    }
    json_bytes = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    json_path = root / "outline.json"
    markdown_path = root / "outline.md"
    _atomic_write(json_path, json_bytes)
    _atomic_write(markdown_path, markdown.encode("utf-8"))
    return json_path, markdown_path
