from __future__ import annotations

import math
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")
Image = pytest.importorskip("PIL.Image")

from rag.pdf_agentic import (
    PdfVisualIndexError,
    expected_asset_count,
    iter_native_page_text,
    load_render_manifest,
    preflight_pdf,
    render_pdf_visual_index,
)


def _write_pdf(path: Path, pages: int, *, width: int = 200, height: int = 300) -> None:
    document = fitz.open()
    for index in range(pages):
        page = document.new_page(width=width, height=height)
        page.insert_text((20, 30), f"native text page {index + 1}")
    document.save(path)
    document.close()


@pytest.mark.parametrize(
    ("page_count", "expected"),
    [(0, 0), (1, 3), (2, 4), (3, 6), (4, 7), (5, 10), (9, 17)],
)
def test_expected_asset_count_formula(page_count: int, expected: int) -> None:
    assert expected_asset_count(page_count) == expected


def test_streaming_renderer_writes_decodable_aligned_lods_and_native_text(
    tmp_path,
) -> None:
    pdf_path = tmp_path / "book.pdf"
    output = tmp_path / "private" / "staging"
    _write_pdf(pdf_path, 5)
    progress: list[tuple[int, int]] = []

    manifest = render_pdf_visual_index(
        pdf_path,
        output,
        render_dpi=72,
        render_max_pixels=100_000,
        lod_max_side=500,
        max_image_bytes=200_000,
        max_derived_bytes=10_000_000,
        min_free_disk_bytes=0,
        on_progress=lambda done, total: progress.append((done, total)),
    )

    assert manifest.page_count == 5
    assert manifest.asset_count == 5 + math.ceil(5 / 2) + math.ceil(5 / 4)
    assert progress == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]
    assert [
        (asset.physical_page_start, asset.physical_page_end)
        for asset in manifest.assets
        if asset.pages_per_image == 2
    ] == [(1, 2), (3, 4), (5, 5)]
    assert [
        (asset.physical_page_start, asset.physical_page_end)
        for asset in manifest.assets
        if asset.pages_per_image == 4
    ] == [(1, 4), (5, 5)]
    pair = manifest.find_asset(2, 1)
    four_up = manifest.find_asset(4, 1)
    tail_four_up = manifest.find_asset(4, 5)
    assert pair is not None and pair.width > pair.height
    assert four_up is not None and four_up.height > four_up.width
    assert tail_four_up is not None and tail_four_up.height > tail_four_up.width

    for asset in manifest.assets:
        path = output / asset.relative_path
        assert path.stat().st_size == asset.byte_size <= 200_000
        with Image.open(path) as image:
            assert image.format == "WEBP"
            assert image.width == asset.width
            assert image.height == asset.height
            if asset.pages_per_image in (2, 4):
                assert max(image.size) <= 500

    single = manifest.find_asset(1, 1)
    assert single is not None
    with Image.open(output / single.relative_path).convert("RGB") as page_image:
        # Source page is 300 px at 72 DPI; the label lives in an appended strip.
        assert page_image.height > 300
        label_strip = page_image.crop((0, 300, page_image.width, page_image.height))
        dark_pixels = sum(1 for pixel in label_strip.getdata() if max(pixel) < 100)
        assert dark_pixels > 5

    native = list(iter_native_page_text(output / manifest.native_text_jsonl))
    assert [record.physical_page for record in native] == [1, 2, 3, 4, 5]
    assert "native text page 5" in native[-1].text
    assert load_render_manifest(output) == manifest


def test_manifest_loader_rejects_tampered_asset(tmp_path) -> None:
    pdf_path = tmp_path / "book.pdf"
    output = tmp_path / "staging"
    _write_pdf(pdf_path, 1)
    manifest = render_pdf_visual_index(
        pdf_path,
        output,
        render_dpi=36,
        render_max_pixels=50_000,
        max_image_bytes=100_000,
        max_derived_bytes=2_000_000,
        min_free_disk_bytes=0,
    )
    asset_path = output / manifest.assets[0].relative_path
    asset_path.write_bytes(asset_path.read_bytes() + b"tampered")

    with pytest.raises(PdfVisualIndexError) as captured:
        load_render_manifest(output)
    assert captured.value.error_code == "pdf_manifest_invalid"


def test_renderer_checks_cancellation_before_each_page(tmp_path) -> None:
    pdf_path = tmp_path / "book.pdf"
    output = tmp_path / "staging"
    _write_pdf(pdf_path, 3)
    checks = 0

    def should_cancel() -> bool:
        nonlocal checks
        checks += 1
        return checks == 2

    with pytest.raises(PdfVisualIndexError) as captured:
        render_pdf_visual_index(
            pdf_path,
            output,
            render_dpi=36,
            render_max_pixels=50_000,
            max_image_bytes=100_000,
            max_derived_bytes=2_000_000,
            min_free_disk_bytes=0,
            should_cancel=should_cancel,
        )
    assert captured.value.error_code == "pdf_processing_cancelled"
    assert not (output / "manifest.json").exists()


def test_preflight_has_stable_codes_for_missing_corrupt_encrypted_and_page_limit(
    tmp_path,
) -> None:
    with pytest.raises(PdfVisualIndexError) as missing:
        preflight_pdf(tmp_path / "missing.pdf")
    assert missing.value.error_code == "pdf_not_found"

    corrupt_path = tmp_path / "corrupt.pdf"
    corrupt_path.write_bytes(b"not a pdf")
    with pytest.raises(PdfVisualIndexError) as corrupt:
        preflight_pdf(corrupt_path)
    assert corrupt.value.error_code == "pdf_open_failed"

    too_long = tmp_path / "two-pages.pdf"
    _write_pdf(too_long, 2)
    with pytest.raises(PdfVisualIndexError) as page_limit:
        preflight_pdf(too_long, max_pages=1)
    assert page_limit.value.error_code == "pdf_page_limit_exceeded"

    plain = fitz.open()
    page = plain.new_page(width=200, height=300)
    page.insert_text((20, 30), "secret")
    encrypted_path = tmp_path / "encrypted.pdf"
    plain.save(
        encrypted_path,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-password",
        user_pw="user-password",
    )
    plain.close()
    with pytest.raises(PdfVisualIndexError) as encrypted:
        preflight_pdf(encrypted_path)
    assert encrypted.value.error_code == "pdf_encrypted"


def test_oversized_rotated_page_is_bounded(tmp_path) -> None:
    pdf_path = tmp_path / "large.pdf"
    document = fitz.open()
    page = document.new_page(width=2_000, height=1_000)
    page.set_rotation(90)
    document.save(pdf_path)
    document.close()

    manifest = render_pdf_visual_index(
        pdf_path,
        tmp_path / "staging",
        render_dpi=160,
        render_max_pixels=20_000,
        lod_max_side=180,
        max_image_bytes=50_000,
        max_derived_bytes=1_000_000,
        min_free_disk_bytes=0,
    )
    single = manifest.find_asset(1, 1)
    assert single is not None
    assert single.width * single.height <= 20_000
