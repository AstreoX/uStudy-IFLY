"""Streaming PDF renderer for private 1-up, 2-up, and 4-up visual assets."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import shutil
from collections.abc import Callable, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .errors import PdfVisualIndexError, PdfVisualIndexErrorCode
from .models import NativePageText, PageAssetManifest, PdfPreflight, RenderManifest

try:  # Keep outline-only users importable when the optional PDF runtime is absent.
    import fitz  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised only in minimal deployments
    fitz = None  # type: ignore[assignment]


DEFAULT_MAX_PAGES = 1_500
DEFAULT_RENDER_DPI = 160
DEFAULT_RENDER_MAX_PIXELS = 8_000_000
DEFAULT_WEBP_QUALITY = 85
DEFAULT_MAX_IMAGE_BYTES = 4 * 1024 * 1024
DEFAULT_LOD_MAX_SIDE = 2_048
DEFAULT_MAX_DERIVED_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_MIN_FREE_DISK_BYTES = 5 * 1024 * 1024 * 1024

ProgressCallback = Callable[[int, int], None]
CancelCallback = Callable[[], bool]


def expected_asset_count(page_count: int) -> int:
    """Return ``N + ceil(N/2) + ceil(N/4)`` for a complete render."""

    if page_count < 0:
        raise ValueError("page_count must be non-negative")
    return page_count + math.ceil(page_count / 2) + math.ceil(page_count / 4)


def _require_fitz() -> Any:
    if fitz is None:
        raise PdfVisualIndexError(
            PdfVisualIndexErrorCode.OPEN_FAILED,
            "PyMuPDF is not installed",
        )
    return fitz


def _open_pdf_path(pdf_path: str | os.PathLike[str]) -> Any:
    fitz_module = _require_fitz()
    path = Path(pdf_path).expanduser().resolve()
    if not path.is_file():
        raise PdfVisualIndexError(
            PdfVisualIndexErrorCode.NOT_FOUND,
            "PDF source file does not exist",
        )
    try:
        # Deliberately pass a path, never an in-memory copy of the whole PDF.
        return fitz_module.open(str(path))
    except Exception as exc:
        raise PdfVisualIndexError(
            PdfVisualIndexErrorCode.OPEN_FAILED,
            "PDF source file could not be opened",
        ) from exc


def _validate_document(doc: Any, pdf_path: Path, max_pages: int) -> PdfPreflight:
    if max_pages < 1:
        raise ValueError("max_pages must be positive")
    if bool(getattr(doc, "needs_pass", False)) or bool(
        getattr(doc, "is_encrypted", False)
    ):
        raise PdfVisualIndexError(
            PdfVisualIndexErrorCode.ENCRYPTED,
            "Encrypted or password-protected PDFs are not supported",
        )

    page_count = int(getattr(doc, "page_count", len(doc)))
    if page_count == 0:
        raise PdfVisualIndexError(
            PdfVisualIndexErrorCode.EMPTY,
            "PDF contains no pages",
        )
    if page_count > max_pages:
        raise PdfVisualIndexError(
            PdfVisualIndexErrorCode.PAGE_LIMIT_EXCEEDED,
            f"PDF exceeds the {max_pages}-page processing limit",
        )

    for page_index in range(page_count):
        try:
            rect = doc.load_page(page_index).rect
            width = float(rect.width)
            height = float(rect.height)
        except Exception as exc:
            raise PdfVisualIndexError(
                PdfVisualIndexErrorCode.OPEN_FAILED,
                f"PDF page {page_index + 1} could not be read",
            ) from exc
        if (
            not math.isfinite(width)
            or not math.isfinite(height)
            or width <= 0
            or height <= 0
        ):
            raise PdfVisualIndexError(
                PdfVisualIndexErrorCode.INVALID_PAGE_SIZE,
                f"PDF page {page_index + 1} has invalid dimensions",
            )

    return PdfPreflight(pdf_path=pdf_path, page_count=page_count)


def preflight_pdf(
    pdf_path: str | os.PathLike[str], *, max_pages: int = DEFAULT_MAX_PAGES
) -> PdfPreflight:
    """Open and validate a PDF directly from a controlled filesystem path."""

    resolved = Path(pdf_path).expanduser().resolve()
    doc = _open_pdf_path(resolved)
    try:
        return _validate_document(doc, resolved, max_pages)
    finally:
        doc.close()


def _nearest_existing_path(path: Path) -> Path:
    candidate = path.expanduser().resolve()
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def _ensure_capacity(root: Path, min_free_bytes: int, incoming_bytes: int = 0) -> None:
    if min_free_bytes < 0:
        raise ValueError("min_free_disk_bytes must be non-negative")
    try:
        free = shutil.disk_usage(_nearest_existing_path(root)).free
    except OSError as exc:
        raise PdfVisualIndexError(
            PdfVisualIndexErrorCode.STORAGE_FAILED,
            "Unable to inspect visual-index storage",
            retryable=True,
        ) from exc
    if free - incoming_bytes < min_free_bytes:
        raise PdfVisualIndexError(
            PdfVisualIndexErrorCode.INSUFFICIENT_DISK,
            "Insufficient free disk space for PDF visual indexing",
            retryable=True,
        )


def _check_derived_budget(current: int, incoming: int, maximum: int) -> None:
    if maximum < 1:
        raise ValueError("max_derived_bytes must be positive")
    if incoming < 0 or current + incoming > maximum:
        raise PdfVisualIndexError(
            PdfVisualIndexErrorCode.DERIVED_SIZE_EXCEEDED,
            "PDF visual index exceeds the derived-file size limit",
        )


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    try:
        with temp_path.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except OSError as exc:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise PdfVisualIndexError(
            PdfVisualIndexErrorCode.STORAGE_FAILED,
            "Failed to persist a PDF visual-index artifact",
            retryable=True,
        ) from exc


def _font_for_label(label_height: int) -> ImageFont.ImageFont:
    size = max(12, min(48, label_height - 8))
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10 compatibility
        return ImageFont.load_default()


def _fit_max_pixels(image: Image.Image, max_pixels: int) -> Image.Image:
    if max_pixels < 1:
        raise ValueError("render_max_pixels must be positive")
    pixels = image.width * image.height
    if pixels <= max_pixels:
        return image
    scale = math.sqrt(max_pixels / pixels)
    size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    resized = image.resize(size, Image.Resampling.LANCZOS)
    image.close()
    return resized


def _add_physical_page_label(
    image: Image.Image, physical_page: int, max_pixels: int
) -> Image.Image:
    label_height = max(28, min(72, round(image.height * 0.025)))
    labeled = Image.new("RGB", (image.width, image.height + label_height), "white")
    labeled.paste(image, (0, 0))
    draw = ImageDraw.Draw(labeled)
    draw.line((0, image.height, image.width, image.height), fill="#B8B8B8", width=1)
    text = f"PDF physical page {physical_page}"
    font = _font_for_label(label_height)
    box = draw.textbbox((0, 0), text, font=font)
    x = max(4, (image.width - (box[2] - box[0])) // 2)
    y = image.height + max(2, (label_height - (box[3] - box[1])) // 2 - box[1])
    draw.text((x, y), text, fill="black", font=font)
    image.close()
    return _fit_max_pixels(labeled, max_pixels)


def _render_page(
    page: Any,
    physical_page: int,
    *,
    render_dpi: int,
    render_max_pixels: int,
) -> Image.Image:
    if render_dpi < 1:
        raise ValueError("render_dpi must be positive")
    rect = page.rect
    zoom = render_dpi / 72.0
    predicted_pixels = max(1.0, float(rect.width) * zoom) * max(
        1.0, float(rect.height) * zoom
    )
    if predicted_pixels > render_max_pixels:
        zoom *= math.sqrt(render_max_pixels / predicted_pixels)
    try:
        pixmap = page.get_pixmap(
            matrix=_require_fitz().Matrix(zoom, zoom),
            colorspace=_require_fitz().csRGB,
            alpha=False,
        )
        image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        del pixmap
        image = _fit_max_pixels(image, render_max_pixels)
        return _add_physical_page_label(image, physical_page, render_max_pixels)
    except PdfVisualIndexError:
        raise
    except Exception as exc:
        raise PdfVisualIndexError(
            PdfVisualIndexErrorCode.PAGE_RENDER_FAILED,
            f"Failed to render PDF page {physical_page}",
        ) from exc


def _compose_lod(
    page_images: list[Image.Image],
    *,
    pages_per_image: int,
    max_side: int,
) -> Image.Image:
    if pages_per_image not in (2, 4):
        raise ValueError("pages_per_image must be 2 or 4")
    if not page_images or len(page_images) > pages_per_image:
        raise ValueError("invalid number of page images")
    if max_side < 1:
        raise ValueError("lod_max_side must be positive")

    columns = 2
    rows = 1 if pages_per_image == 2 else 2
    gutter = 12
    max_width = max(image.width for image in page_images)
    max_height = max(image.height for image in page_images)
    natural_width = columns * max_width + (columns - 1) * gutter
    natural_height = rows * max_height + (rows - 1) * gutter
    scale = min(1.0, max_side / max(natural_width, natural_height))
    cell_width = max(1, int(max_width * scale))
    cell_height = max(1, int(max_height * scale))
    scaled_gutter = max(1, int(gutter * scale))
    canvas = Image.new(
        "RGB",
        (
            columns * cell_width + (columns - 1) * scaled_gutter,
            rows * cell_height + (rows - 1) * scaled_gutter,
        ),
        "#E7E7E7",
    )

    for index, image in enumerate(page_images):
        fitted = image.copy()
        fitted.thumbnail((cell_width, cell_height), Image.Resampling.LANCZOS)
        row, column = divmod(index, columns)
        x = column * (cell_width + scaled_gutter) + (cell_width - fitted.width) // 2
        y = row * (cell_height + scaled_gutter) + (cell_height - fitted.height) // 2
        canvas.paste(fitted, (x, y))
        fitted.close()
    return canvas


def _encode_webp_limited(
    source: Image.Image,
    *,
    preferred_quality: int,
    max_bytes: int,
) -> tuple[bytes, int, int]:
    if not 1 <= preferred_quality <= 100:
        raise ValueError("webp_quality must be between 1 and 100")
    if max_bytes < 1:
        raise ValueError("max_image_bytes must be positive")

    qualities: list[int] = []
    for quality in (
        preferred_quality,
        min(preferred_quality, 78),
        min(preferred_quality, 70),
    ):
        if quality not in qualities:
            qualities.append(quality)

    candidate = source.copy()
    try:
        for resize_round in range(21):
            round_qualities = qualities if resize_round == 0 else [qualities[-1]]
            for quality in round_qualities:
                buffer = io.BytesIO()
                candidate.save(buffer, format="WEBP", quality=quality, method=6)
                encoded = buffer.getvalue()
                if len(encoded) <= max_bytes:
                    # Decode once before publishing; a corrupt/unsupported WebP is fatal.
                    with Image.open(io.BytesIO(encoded)) as verification:
                        verification.verify()
                    return encoded, candidate.width, candidate.height

            if candidate.width <= 64 and candidate.height <= 64:
                break
            next_size = (
                max(1, int(candidate.width * 0.85)),
                max(1, int(candidate.height * 0.85)),
            )
            resized = candidate.resize(next_size, Image.Resampling.LANCZOS)
            candidate.close()
            candidate = resized
    except OSError as exc:
        raise PdfVisualIndexError(
            PdfVisualIndexErrorCode.PAGE_RENDER_FAILED,
            "WebP encoding failed",
        ) from exc
    finally:
        candidate.close()

    raise PdfVisualIndexError(
        PdfVisualIndexErrorCode.IMAGE_LIMIT_EXCEEDED,
        "Rendered page image cannot fit within the per-image byte limit",
    )


def _asset_relative_path(pages_per_image: int, start: int, end: int) -> str:
    if pages_per_image == 1:
        filename = f"page-{start:06d}.webp"
    else:
        filename = f"pages-{start:06d}-{end:06d}.webp"
    return (Path("pages") / str(pages_per_image) / filename).as_posix()


def _persist_image_asset(
    image: Image.Image,
    *,
    root: Path,
    pages_per_image: int,
    start: int,
    end: int,
    preferred_quality: int,
    max_image_bytes: int,
    current_derived_bytes: int,
    max_derived_bytes: int,
    min_free_disk_bytes: int,
) -> PageAssetManifest:
    encoded, width, height = _encode_webp_limited(
        image,
        preferred_quality=preferred_quality,
        max_bytes=max_image_bytes,
    )
    _check_derived_budget(current_derived_bytes, len(encoded), max_derived_bytes)
    _ensure_capacity(root, min_free_disk_bytes, len(encoded))
    relative_path = _asset_relative_path(pages_per_image, start, end)
    _atomic_write_bytes(root / relative_path, encoded)
    return PageAssetManifest(
        pages_per_image=pages_per_image,  # type: ignore[arg-type]
        physical_page_start=start,
        physical_page_end=end,
        relative_path=relative_path,
        mime_type="image/webp",
        width=width,
        height=height,
        byte_size=len(encoded),
        sha256=hashlib.sha256(encoded).hexdigest(),
    )


def _manifest_bytes(manifest: RenderManifest) -> bytes:
    return (
        json.dumps(
            manifest.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _validate_render_options(
    *,
    max_pages: int,
    render_dpi: int,
    render_max_pixels: int,
    webp_quality: int,
    max_image_bytes: int,
    lod_max_side: int,
    max_derived_bytes: int,
    min_free_disk_bytes: int,
) -> None:
    positive = {
        "max_pages": max_pages,
        "render_dpi": render_dpi,
        "render_max_pixels": render_max_pixels,
        "max_image_bytes": max_image_bytes,
        "lod_max_side": lod_max_side,
        "max_derived_bytes": max_derived_bytes,
    }
    for name, value in positive.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if not isinstance(webp_quality, int) or isinstance(webp_quality, bool):
        raise TypeError("webp_quality must be an integer")
    if not 1 <= webp_quality <= 100:
        raise ValueError("webp_quality must be between 1 and 100")
    if (
        not isinstance(min_free_disk_bytes, int)
        or isinstance(min_free_disk_bytes, bool)
        or min_free_disk_bytes < 0
    ):
        raise ValueError("min_free_disk_bytes must be a non-negative integer")


def render_pdf_visual_index(
    pdf_path: str | os.PathLike[str],
    staging_root: str | os.PathLike[str],
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    render_dpi: int = DEFAULT_RENDER_DPI,
    render_max_pixels: int = DEFAULT_RENDER_MAX_PIXELS,
    webp_quality: int = DEFAULT_WEBP_QUALITY,
    max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
    lod_max_side: int = DEFAULT_LOD_MAX_SIDE,
    max_derived_bytes: int = DEFAULT_MAX_DERIVED_BYTES,
    min_free_disk_bytes: int = DEFAULT_MIN_FREE_DISK_BYTES,
    on_progress: ProgressCallback | None = None,
    should_cancel: CancelCallback | None = None,
) -> RenderManifest:
    """Render all LODs with at most four source-page PIL images resident at once.

    The caller owns the generation-specific staging directory. Files are always
    written as ``*.tmp`` and atomically replaced in place; the returned manifest
    is emitted only after every required asset has been encoded and persisted.
    """

    _validate_render_options(
        max_pages=max_pages,
        render_dpi=render_dpi,
        render_max_pixels=render_max_pixels,
        webp_quality=webp_quality,
        max_image_bytes=max_image_bytes,
        lod_max_side=lod_max_side,
        max_derived_bytes=max_derived_bytes,
        min_free_disk_bytes=min_free_disk_bytes,
    )
    root = Path(staging_root).expanduser().resolve()
    source = Path(pdf_path).expanduser().resolve()
    _ensure_capacity(root, min_free_disk_bytes)
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PdfVisualIndexError(
            PdfVisualIndexErrorCode.STORAGE_FAILED,
            "Unable to create PDF visual-index staging directory",
            retryable=True,
        ) from exc

    doc = _open_pdf_path(source)
    native_relative_path = "native_text.jsonl"
    native_final_path = root / native_relative_path
    native_temp_path = native_final_path.with_name(f"{native_final_path.name}.tmp")
    assets: list[PageAssetManifest] = []
    derived_bytes = 0
    native_nonempty_count = 0

    try:
        preflight = _validate_document(doc, source, max_pages)
        try:
            native_handle = native_temp_path.open("wb")
        except OSError as exc:
            raise PdfVisualIndexError(
                PdfVisualIndexErrorCode.STORAGE_FAILED,
                "Unable to create native-text checkpoint",
                retryable=True,
            ) from exc

        with native_handle:
            for block_start_index in range(0, preflight.page_count, 4):
                page_images: list[Image.Image] = []
                try:
                    block_end_index = min(block_start_index + 4, preflight.page_count)
                    for page_index in range(block_start_index, block_end_index):
                        physical_page = page_index + 1
                        if should_cancel is not None and should_cancel():
                            raise PdfVisualIndexError(
                                PdfVisualIndexErrorCode.CANCELLED,
                                "PDF visual indexing was cancelled",
                                retryable=True,
                            )
                        page = doc.load_page(page_index)
                        try:
                            native_text = page.get_text("text", sort=True) or ""
                        except Exception:  # noqa: BLE001 - preserve scan-only pages
                            native_text = ""
                        if native_text.strip():
                            native_nonempty_count += 1
                        text_line = (
                            json.dumps(
                                {
                                    "physical_page": physical_page,
                                    "text": native_text,
                                },
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                            + "\n"
                        ).encode("utf-8")
                        _check_derived_budget(
                            derived_bytes, len(text_line), max_derived_bytes
                        )
                        _ensure_capacity(root, min_free_disk_bytes, len(text_line))
                        try:
                            native_handle.write(text_line)
                        except OSError as exc:
                            raise PdfVisualIndexError(
                                PdfVisualIndexErrorCode.STORAGE_FAILED,
                                "Failed to write native-text checkpoint",
                                retryable=True,
                            ) from exc
                        derived_bytes += len(text_line)

                        image = _render_page(
                            page,
                            physical_page,
                            render_dpi=render_dpi,
                            render_max_pixels=render_max_pixels,
                        )
                        page_images.append(image)
                        asset = _persist_image_asset(
                            image,
                            root=root,
                            pages_per_image=1,
                            start=physical_page,
                            end=physical_page,
                            preferred_quality=webp_quality,
                            max_image_bytes=max_image_bytes,
                            current_derived_bytes=derived_bytes,
                            max_derived_bytes=max_derived_bytes,
                            min_free_disk_bytes=min_free_disk_bytes,
                        )
                        assets.append(asset)
                        derived_bytes += asset.byte_size
                        if on_progress is not None:
                            on_progress(physical_page, preflight.page_count)

                    for pair_offset in range(0, len(page_images), 2):
                        pair = page_images[pair_offset : pair_offset + 2]
                        start = block_start_index + pair_offset + 1
                        end = start + len(pair) - 1
                        composite = _compose_lod(
                            pair,
                            pages_per_image=2,
                            max_side=lod_max_side,
                        )
                        try:
                            asset = _persist_image_asset(
                                composite,
                                root=root,
                                pages_per_image=2,
                                start=start,
                                end=end,
                                preferred_quality=webp_quality,
                                max_image_bytes=max_image_bytes,
                                current_derived_bytes=derived_bytes,
                                max_derived_bytes=max_derived_bytes,
                                min_free_disk_bytes=min_free_disk_bytes,
                            )
                        finally:
                            composite.close()
                        assets.append(asset)
                        derived_bytes += asset.byte_size

                    start = block_start_index + 1
                    end = block_start_index + len(page_images)
                    composite = _compose_lod(
                        page_images,
                        pages_per_image=4,
                        max_side=lod_max_side,
                    )
                    try:
                        asset = _persist_image_asset(
                            composite,
                            root=root,
                            pages_per_image=4,
                            start=start,
                            end=end,
                            preferred_quality=webp_quality,
                            max_image_bytes=max_image_bytes,
                            current_derived_bytes=derived_bytes,
                            max_derived_bytes=max_derived_bytes,
                            min_free_disk_bytes=min_free_disk_bytes,
                        )
                    finally:
                        composite.close()
                    assets.append(asset)
                    derived_bytes += asset.byte_size
                finally:
                    for image in page_images:
                        image.close()

            try:
                native_handle.flush()
                os.fsync(native_handle.fileno())
            except OSError as exc:
                raise PdfVisualIndexError(
                    PdfVisualIndexErrorCode.STORAGE_FAILED,
                    "Failed to flush native-text checkpoint",
                    retryable=True,
                ) from exc

        try:
            os.replace(native_temp_path, native_final_path)
        except OSError as exc:
            raise PdfVisualIndexError(
                PdfVisualIndexErrorCode.STORAGE_FAILED,
                "Failed to publish native-text checkpoint",
                retryable=True,
            ) from exc

        manifest = RenderManifest(
            schema_version=1,
            page_count=preflight.page_count,
            render_dpi=render_dpi,
            render_max_pixels=render_max_pixels,
            webp_quality=webp_quality,
            max_image_bytes=max_image_bytes,
            lod_max_side=lod_max_side,
            native_text_jsonl=native_relative_path,
            native_text_page_count=preflight.page_count,
            native_text_nonempty_page_count=native_nonempty_count,
            assets=tuple(assets),
            derived_bytes=derived_bytes,
        )
        # Include the manifest itself in the reported derived byte count. Iterate
        # until the encoded integer width no longer changes the serialized size.
        base_bytes = derived_bytes
        for _ in range(4):
            encoded_manifest = _manifest_bytes(manifest)
            next_total = base_bytes + len(encoded_manifest)
            if next_total == manifest.derived_bytes:
                break
            manifest = replace(manifest, derived_bytes=next_total)
        encoded_manifest = _manifest_bytes(manifest)
        _check_derived_budget(base_bytes, len(encoded_manifest), max_derived_bytes)
        _ensure_capacity(root, min_free_disk_bytes, len(encoded_manifest))
        _atomic_write_bytes(root / manifest.manifest_path, encoded_manifest)

        if len(assets) != expected_asset_count(preflight.page_count):
            raise PdfVisualIndexError(
                PdfVisualIndexErrorCode.STORAGE_FAILED,
                "Incomplete PDF visual-index manifest",
            )
        return manifest
    finally:
        doc.close()


def iter_native_page_text(
    jsonl_path: str | os.PathLike[str],
) -> Iterator[NativePageText]:
    """Stream native page text records back from a renderer checkpoint."""

    with Path(jsonl_path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                physical_page = value["physical_page"]
                text = value["text"]
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"invalid native-text JSONL at line {line_number}"
                ) from exc
            if (
                not isinstance(physical_page, int)
                or isinstance(physical_page, bool)
                or physical_page < 1
                or not isinstance(text, str)
            ):
                raise ValueError(f"invalid native-text JSONL at line {line_number}")
            yield NativePageText(physical_page=physical_page, text=text)


def _manifest_error(
    message: str, cause: BaseException | None = None
) -> PdfVisualIndexError:
    error = PdfVisualIndexError(
        PdfVisualIndexErrorCode.MANIFEST_INVALID,
        message,
    )
    if cause is not None:
        error.__cause__ = cause
    return error


def _strict_manifest_int(value: Any, name: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise _manifest_error(f"Manifest field {name} is invalid")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_render_manifest(
    staging_root: str | os.PathLike[str],
) -> RenderManifest:
    """Load and fully validate a completed render for safe retry reuse.

    Validation covers the manifest schema, exact LOD grouping, relative-path
    containment, every asset's size and SHA-256, native-text page order, and the
    total derived byte count. A partial generation is never accepted.
    """

    root = Path(staging_root).expanduser().resolve()
    manifest_path = root / "manifest.json"
    try:
        manifest_bytes = manifest_path.read_bytes()
        value = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise _manifest_error("Render manifest is missing or malformed", exc)
    if not isinstance(value, dict):
        raise _manifest_error("Render manifest must be a JSON object")
    try:
        page_count = _strict_manifest_int(
            value.get("page_count"), "page_count", minimum=1
        )
        schema_version = _strict_manifest_int(
            value.get("schema_version"), "schema_version", minimum=1
        )
        if schema_version != 1:
            raise _manifest_error("Unsupported render manifest schema version")
        if value.get("manifest_path") != "manifest.json":
            raise _manifest_error("Manifest path marker is invalid")
        raw_assets = value.get("assets")
        if not isinstance(raw_assets, list):
            raise _manifest_error("Manifest assets must be an array")
        declared_asset_count = _strict_manifest_int(
            value.get("asset_count"), "asset_count", minimum=1
        )
        if declared_asset_count != len(raw_assets):
            raise _manifest_error("Manifest asset counter is inconsistent")
        assets: list[PageAssetManifest] = []
        seen_keys: set[tuple[int, int]] = set()
        asset_bytes = 0
        for raw_asset in raw_assets:
            if not isinstance(raw_asset, dict):
                raise _manifest_error("Manifest asset entry must be an object")
            lod = _strict_manifest_int(
                raw_asset.get("pages_per_image"), "pages_per_image", minimum=1
            )
            if lod not in (1, 2, 4):
                raise _manifest_error("Manifest asset LOD must be 1, 2, or 4")
            start = _strict_manifest_int(
                raw_asset.get("physical_page_start"),
                "physical_page_start",
                minimum=1,
            )
            end = _strict_manifest_int(
                raw_asset.get("physical_page_end"),
                "physical_page_end",
                minimum=1,
            )
            expected_start = ((start - 1) // lod) * lod + 1
            expected_end = min(start + lod - 1, page_count)
            if start != expected_start or end != expected_end:
                raise _manifest_error(
                    "Manifest asset has an invalid aligned page range"
                )
            key = (lod, start)
            if key in seen_keys:
                raise _manifest_error("Manifest contains a duplicate page asset")
            seen_keys.add(key)
            relative_path = raw_asset.get("relative_path")
            mime_type = raw_asset.get("mime_type")
            checksum = raw_asset.get("sha256")
            if not isinstance(relative_path, str) or not relative_path:
                raise _manifest_error("Manifest asset path is invalid")
            if mime_type != "image/webp":
                raise _manifest_error("Manifest asset MIME type is invalid")
            if (
                not isinstance(checksum, str)
                or len(checksum) != 64
                or any(char not in "0123456789abcdef" for char in checksum)
            ):
                raise _manifest_error("Manifest asset checksum is invalid")
            width = _strict_manifest_int(raw_asset.get("width"), "width", minimum=1)
            height = _strict_manifest_int(raw_asset.get("height"), "height", minimum=1)
            byte_size = _strict_manifest_int(
                raw_asset.get("byte_size"), "byte_size", minimum=1
            )
            candidate = (root / relative_path).resolve()
            try:
                contained = (
                    Path(os.path.commonpath((str(root), str(candidate)))) == root
                )
            except ValueError:
                contained = False
            if not contained or not candidate.is_file():
                raise _manifest_error("Manifest asset is missing or outside its root")
            try:
                actual_size = candidate.stat().st_size
                actual_checksum = _sha256_file(candidate)
            except OSError as exc:
                raise _manifest_error("Manifest asset could not be read", exc)
            if actual_size != byte_size or actual_checksum != checksum:
                raise _manifest_error("Manifest asset integrity check failed")
            try:
                with Image.open(candidate) as decoded:
                    if decoded.format != "WEBP" or decoded.size != (width, height):
                        raise _manifest_error("Manifest image metadata is inconsistent")
                    decoded.verify()
            except (OSError, SyntaxError) as exc:
                raise _manifest_error("Manifest asset is not a valid WebP image", exc)
            assets.append(
                PageAssetManifest(
                    pages_per_image=lod,  # type: ignore[arg-type]
                    physical_page_start=start,
                    physical_page_end=end,
                    relative_path=relative_path,
                    mime_type=mime_type,
                    width=width,
                    height=height,
                    byte_size=byte_size,
                    sha256=checksum,
                )
            )
            asset_bytes += byte_size

        if len(assets) != expected_asset_count(page_count):
            raise _manifest_error("Manifest does not contain every required LOD asset")
        for lod in (1, 2, 4):
            for start in range(1, page_count + 1, lod):
                if (lod, start) not in seen_keys:
                    raise _manifest_error(
                        "Manifest is missing a required aligned LOD asset"
                    )

        native_relative = value.get("native_text_jsonl")
        if not isinstance(native_relative, str) or not native_relative:
            raise _manifest_error("Manifest native-text path is invalid")
        native_path = (root / native_relative).resolve()
        try:
            native_contained = (
                Path(os.path.commonpath((str(root), str(native_path)))) == root
            )
        except ValueError:
            native_contained = False
        if not native_contained or not native_path.is_file():
            raise _manifest_error(
                "Native-text checkpoint is missing or outside its root"
            )
        native_page_count = 0
        nonempty_count = 0
        for expected_page, record in enumerate(
            iter_native_page_text(native_path), start=1
        ):
            if record.physical_page != expected_page:
                raise _manifest_error(
                    "Native-text checkpoint has incomplete page ordering"
                )
            native_page_count += 1
            nonempty_count += bool(record.text.strip())
        if native_page_count != page_count:
            raise _manifest_error("Native-text checkpoint has incomplete page ordering")
        declared_native_pages = _strict_manifest_int(
            value.get("native_text_page_count"),
            "native_text_page_count",
            minimum=0,
        )
        declared_nonempty = _strict_manifest_int(
            value.get("native_text_nonempty_page_count"),
            "native_text_nonempty_page_count",
            minimum=0,
        )
        if declared_native_pages != page_count or declared_nonempty != nonempty_count:
            raise _manifest_error("Native-text manifest counters are inconsistent")

        derived_bytes = _strict_manifest_int(
            value.get("derived_bytes"), "derived_bytes", minimum=1
        )
        actual_total = asset_bytes + native_path.stat().st_size + len(manifest_bytes)
        if derived_bytes != actual_total:
            raise _manifest_error("Manifest derived byte total is inconsistent")
        render_max_pixels = _strict_manifest_int(
            value.get("render_max_pixels"), "render_max_pixels", minimum=1
        )
        webp_quality = _strict_manifest_int(
            value.get("webp_quality"), "webp_quality", minimum=1
        )
        max_image_bytes = _strict_manifest_int(
            value.get("max_image_bytes"), "max_image_bytes", minimum=1
        )
        lod_max_side = _strict_manifest_int(
            value.get("lod_max_side"), "lod_max_side", minimum=1
        )
        if webp_quality > 100:
            raise _manifest_error("Manifest WebP quality is invalid")
        if any(asset.byte_size > max_image_bytes for asset in assets):
            raise _manifest_error("Manifest asset exceeds its image byte limit")
        if any(
            asset.pages_per_image == 1
            and asset.width * asset.height > render_max_pixels
            for asset in assets
        ):
            raise _manifest_error("Manifest single-page asset exceeds its pixel limit")
        if any(
            asset.pages_per_image in (2, 4)
            and max(asset.width, asset.height) > lod_max_side
            for asset in assets
        ):
            raise _manifest_error("Manifest LOD asset exceeds its side limit")
        manifest = RenderManifest(
            schema_version=schema_version,
            page_count=page_count,
            render_dpi=_strict_manifest_int(
                value.get("render_dpi"), "render_dpi", minimum=1
            ),
            render_max_pixels=render_max_pixels,
            webp_quality=webp_quality,
            max_image_bytes=max_image_bytes,
            lod_max_side=lod_max_side,
            native_text_jsonl=native_relative,
            native_text_page_count=declared_native_pages,
            native_text_nonempty_page_count=declared_nonempty,
            assets=tuple(assets),
            derived_bytes=derived_bytes,
            manifest_path="manifest.json",
        )
    except PdfVisualIndexError:
        raise
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise _manifest_error("Render manifest validation failed", exc)
    return manifest
