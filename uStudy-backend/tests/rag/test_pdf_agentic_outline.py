from __future__ import annotations

import json

import pytest

from rag.pdf_agentic import (
    NumericPageAnchor,
    OutlineEntry,
    TocModelResponseError,
    compute_page_offset,
    merge_outline_entries,
    parse_model_json,
    parse_toc_page_response,
    render_outline_markdown,
    resolve_outline_entries,
    sanitize_title,
    write_outline_artifacts,
)


def test_parse_model_json_accepts_only_plain_or_fenced_object() -> None:
    assert parse_model_json('```json\n{"entries": []}\n```') == {"entries": []}
    with pytest.raises(TocModelResponseError):
        parse_model_json('result: {"entries": []}')
    with pytest.raises(TocModelResponseError):
        parse_model_json('{"entries": [}')
    with pytest.raises(TocModelResponseError):
        parse_model_json("[]")


def test_toc_page_parser_sanitizes_derives_numeric_label_and_merges_duplicates() -> (
    None
):
    first = parse_toc_page_response(
        json.dumps(
            {
                "entries": [
                    {
                        "title": "  <Intro> *start*\n\u0000 ",
                        "level": 1,
                        "printed_page_label": "1",
                        "printed_page_number": None,
                    }
                ],
                "continues": True,
            }
        ),
        3,
    )
    second = parse_toc_page_response(
        json.dumps(
            {
                "entries": [
                    {
                        "title": "<Intro> *start*",
                        "level": 2,
                        "printed_page_label": "1",
                        "printed_page_number": 1,
                    },
                    {
                        "title": "Appendix",
                        "level": 1,
                        "printed_page_label": "xii",
                        "printed_page_number": None,
                    },
                ],
                "continues": False,
            }
        ),
        4,
    )

    assert first.entries[0].printed_page_number == 1
    assert "<" not in first.entries[0].title
    assert "\\*start\\*" in first.entries[0].title
    assert merge_outline_entries([first, second]) == (
        first.entries[0],
        second.entries[1],
    )
    assert sanitize_title("a\u0000\tb") == "a b"


@pytest.mark.parametrize(
    ("anchors", "page_count", "expected"),
    [
        (
            [NumericPageAnchor(1, 8), NumericPageAnchor(2, 9)],
            20,
            7,
        ),
        ([NumericPageAnchor(1, 8)], 20, None),
        (
            [NumericPageAnchor(1, 8), NumericPageAnchor(1, 8)],
            20,
            None,
        ),
        (
            [NumericPageAnchor(1, 8), NumericPageAnchor(2, 10)],
            20,
            None,
        ),
        (
            [NumericPageAnchor(1, 8), NumericPageAnchor(2, 99)],
            20,
            None,
        ),
    ],
)
def test_compute_page_offset_requires_two_distinct_consistent_anchors(
    anchors: list[NumericPageAnchor], page_count: int, expected: int | None
) -> None:
    assert compute_page_offset(anchors, page_count=page_count) == expected


def test_resolve_and_write_deterministic_outline(tmp_path) -> None:
    entries = (
        OutlineEntry("Chapter 1", 1, "1", 1, source_physical_page=3),
        OutlineEntry("Roman preface", 2, "xii", None, source_physical_page=3),
        OutlineEntry("Out of range", 1, "99", 99, source_physical_page=4),
    )
    resolved = resolve_outline_entries(entries, page_offset=7, page_count=20)
    assert [entry.resolved_pdf_page for entry in resolved] == [8, None, None]

    markdown = render_outline_markdown(
        resolved,
        toc_physical_page_start=3,
        toc_physical_page_end=4,
        page_offset=7,
    )
    assert "physical_pdf_page = printed_page_number + page_offset" in markdown
    assert "page_offset: `7`" in markdown
    assert "printed_page_1_pdf_page: `8`" in markdown
    assert "TOC physical page range: `3-4`" in markdown
    assert "PDF physical page `8`" in markdown

    json_path, markdown_path = write_outline_artifacts(
        tmp_path,
        resolved,
        toc_physical_page_start=3,
        toc_physical_page_end=4,
        page_offset=7,
    )
    assert markdown_path.read_text(encoding="utf-8") == markdown
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["mapping_formula"].endswith("+ page_offset")
    assert payload["entries"][0]["resolved_pdf_page"] == 8
