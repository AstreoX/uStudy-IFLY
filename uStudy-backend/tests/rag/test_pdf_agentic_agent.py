from __future__ import annotations

import hashlib
import io
import math
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from rag.pdf_agentic import PageAssetManifest, RenderManifest, TocIndexAgent


def _fake_manifest(root: Path, page_count: int) -> RenderManifest:
    buffer = io.BytesIO()
    Image.new("RGB", (80, 100), "white").save(buffer, "WEBP", quality=80)
    image_bytes = buffer.getvalue()
    checksum = hashlib.sha256(image_bytes).hexdigest()
    assets: list[PageAssetManifest] = []
    for lod in (1, 2, 4):
        for start in range(1, page_count + 1, lod):
            end = min(start + lod - 1, page_count)
            relative = f"pages/{lod}/{start}-{end}.webp"
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(image_bytes)
            assets.append(
                PageAssetManifest(
                    pages_per_image=lod,  # type: ignore[arg-type]
                    physical_page_start=start,
                    physical_page_end=end,
                    relative_path=relative,
                    mime_type="image/webp",
                    width=80,
                    height=100,
                    byte_size=len(image_bytes),
                    sha256=checksum,
                )
            )
    return RenderManifest(
        schema_version=1,
        page_count=page_count,
        render_dpi=160,
        render_max_pixels=8_000_000,
        webp_quality=85,
        max_image_bytes=4 * 1024 * 1024,
        lod_max_side=2048,
        native_text_jsonl="native_text.jsonl",
        native_text_page_count=page_count,
        native_text_nonempty_page_count=0,
        assets=tuple(assets),
        derived_bytes=0,
    )


@pytest.mark.asyncio
async def test_agent_locates_extracts_offsets_and_reuses_checkpoints(tmp_path) -> None:
    manifest = _fake_manifest(tmp_path, 10)
    checkpoints: dict[str, str] = {}
    calls: list[tuple[list[dict[str, Any]], str]] = []

    async def completion(messages: list[dict[str, Any]], call_key: str) -> str:
        calls.append((messages, call_key))
        prompt = messages[1]["content"][0]["text"]
        image_count = sum(
            item["type"] == "image_url" for item in messages[1]["content"]
        )
        assert 1 <= image_count <= 4
        assert "UNTRUSTED DATA" in messages[0]["content"]
        if "Locate the document" in prompt:
            return '{"status":"found","toc_start":2,"toc_end":3,"requests":[]}'
        if "physical page 2" in prompt:
            return (
                '{"entries":[{"title":"Chapter 1","level":1,'
                '"printed_page_label":"1","printed_page_number":1}],'
                '"continues":true}'
            )
        if "physical page 3" in prompt:
            return (
                '{"entries":[{"title":"Chapter 1","level":1,'
                '"printed_page_label":"1","printed_page_number":1},'
                '{"title":"Chapter 2","level":1,'
                '"printed_page_label":"5","printed_page_number":5}],'
                '"continues":false}'
            )
        if "post-TOC content pages" in prompt:
            return (
                '{"anchors":[{"printed_page_number":1,"physical_pdf_page":4},'
                '{"printed_page_number":2,"physical_pdf_page":5}]}'
            )
        raise AssertionError(prompt)

    async def checkpoint_get(key: str) -> str | None:
        return checkpoints.get(key)

    async def checkpoint_put(key: str, value: str) -> None:
        checkpoints[key] = value

    agent = TocIndexAgent(
        completion=completion,
        checkpoint_get=checkpoint_get,
        checkpoint_put=checkpoint_put,
        model="mock-vlm",
        anchor_window_pages=4,
    )
    first = await agent.run("doc-1", 2, manifest, tmp_path)
    assert first.status == "ready"
    assert first.page_offset == 3
    assert first.toc_physical_page_start == 2
    assert first.toc_physical_page_end == 3
    assert [entry.title for entry in first.entries] == ["Chapter 1", "Chapter 2"]
    assert [entry.resolved_pdf_page for entry in first.entries] == [4, 8]
    assert len(calls) == 4
    assert len(checkpoints) == 4
    assert all(key.startswith("pdf-index:doc-1:2:") for key in first.call_keys)

    calls.clear()
    second = await agent.run("doc-1", 2, manifest, tmp_path)
    assert second == first
    assert calls == []


@pytest.mark.asyncio
async def test_agent_scans_later_coarse_batch_before_not_found(tmp_path) -> None:
    manifest = _fake_manifest(tmp_path, 20)
    locate_calls = 0

    async def completion(messages: list[dict[str, Any]], call_key: str) -> str:
        nonlocal locate_calls
        del messages, call_key
        locate_calls += 1
        return '{"status":"not_found","toc_start":null,"toc_end":null,"requests":[]}'

    result = await TocIndexAgent(
        completion=completion,
        model="mock-vlm",
    ).run("doc-2", 1, manifest, tmp_path)
    assert result.status == "not_found"
    assert locate_calls == math.ceil(math.ceil(20 / 4) / 4)


@pytest.mark.asyncio
async def test_agent_returns_failed_after_malformed_json_retries(tmp_path) -> None:
    manifest = _fake_manifest(tmp_path, 2)
    calls = 0

    async def completion(messages: list[dict[str, Any]], call_key: str) -> str:
        nonlocal calls
        del messages, call_key
        calls += 1
        return "not-json"

    result = await TocIndexAgent(
        completion=completion,
        model="mock-vlm",
        completion_attempts=2,
    ).run("doc-3", 1, manifest, tmp_path)
    assert result.status == "failed"
    assert result.error_code == "toc_vlm_failed"
    assert calls == 2
