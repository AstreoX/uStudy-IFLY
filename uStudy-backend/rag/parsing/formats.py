"""Document format resolution and legacy normalization utilities."""

from __future__ import annotations

import io
import logging
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

OLE_MAGIC = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
PDF_MAGIC = b"%PDF"
ZIP_MAGIC = b"PK\x03\x04"

CANONICAL_TYPE_TO_MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text": "text/plain",
    "markdown": "text/markdown",
    "html": "text/html",
    "csv": "text/csv",
    "epub": "application/epub+zip",
}

CANONICAL_TYPE_TO_EXTENSION = {
    "pdf": ".pdf",
    "docx": ".docx",
    "xlsx": ".xlsx",
    "pptx": ".pptx",
    "text": ".txt",
    "markdown": ".md",
    "html": ".html",
    "csv": ".csv",
    "epub": ".epub",
}

TEXT_EXTENSION_TO_TYPE = {
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".html": "html",
    ".htm": "html",
    ".csv": "csv",
}

TEXT_MIME_TO_TYPE = {
    "text/plain": "text",
    "text/markdown": "markdown",
    "text/x-markdown": "markdown",
    "text/html": "html",
    "application/xhtml+xml": "html",
    "text/csv": "csv",
}

CANONICAL_MIME_TO_TYPE = {v: k for k, v in CANONICAL_TYPE_TO_MIME.items()}

LEGACY_EXTENSION_TO_TARGET = {
    ".doc": "docx",
    ".xls": "xlsx",
    ".ppt": "pptx",
}

LEGACY_MIME_TO_TARGET = {
    "application/msword": "docx",
    "application/vnd.ms-excel": "xlsx",
    "application/vnd.ms-powerpoint": "pptx",
}

SUPPORTED_DOCUMENT_EXTENSIONS = sorted(
    {
        *CANONICAL_TYPE_TO_EXTENSION.values(),
        ".htm",
        ".markdown",
        *LEGACY_EXTENSION_TO_TARGET.keys(),
    }
)


class DocumentFormatError(ValueError):
    """Raised when a document format cannot be resolved."""


class LegacyDocumentNormalizationError(ValueError):
    """Raised when a legacy Office file cannot be normalized."""


@dataclass(frozen=True)
class ResolvedDocumentFormat:
    """Resolved document format information."""

    canonical_type: str
    mime_type: str
    extension: str
    source_extension: str
    parser_backend: str
    needs_normalization: bool = False
    legacy_source_type: str | None = None

    @property
    def storage_extension(self) -> str:
        return self.source_extension or self.extension


@dataclass(frozen=True)
class NormalizedDocument:
    """Normalized document payload."""

    content: bytes
    filename: str
    resolved_format: ResolvedDocumentFormat
    normalized: bool = False


def get_supported_document_mime_types() -> list[str]:
    """Return canonical MIME types accepted by the document pipeline."""
    return sorted(CANONICAL_MIME_TO_TYPE.keys())


def get_supported_document_extensions() -> list[str]:
    """Return supported source extensions, including legacy Office formats."""
    return SUPPORTED_DOCUMENT_EXTENSIONS[:]


def canonical_type_from_hint(format_hint: str) -> str:
    """Resolve canonical document type from a canonical type or MIME hint."""
    hint = (format_hint or "").strip().lower()
    if hint in CANONICAL_TYPE_TO_MIME:
        return hint
    if hint in CANONICAL_MIME_TO_TYPE:
        return CANONICAL_MIME_TO_TYPE[hint]
    if hint in LEGACY_MIME_TO_TARGET:
        return LEGACY_MIME_TO_TARGET[hint]
    raise DocumentFormatError(f"不支持的文件类型: {format_hint}")


def get_canonical_mime(format_hint: str) -> str:
    """Resolve canonical MIME type from a type or MIME hint."""
    return CANONICAL_TYPE_TO_MIME[canonical_type_from_hint(format_hint)]


def resolve_document_format(
    file_bytes: bytes,
    filename: str | None = None,
    claimed_mime: str | None = None,
) -> ResolvedDocumentFormat:
    """Resolve a file into a canonical document format."""
    suffix = Path(filename or "").suffix.lower()
    claimed = (claimed_mime or "").split(";")[0].strip().lower()

    if file_bytes.startswith(PDF_MAGIC):
        return _build_resolved("pdf", suffix or ".pdf")

    if file_bytes.startswith(ZIP_MAGIC):
        ooxml_type = _detect_zip_document_type(file_bytes, suffix)
        if ooxml_type:
            return _build_resolved(ooxml_type, suffix or CANONICAL_TYPE_TO_EXTENSION[ooxml_type])

    if file_bytes.startswith(OLE_MAGIC):
        legacy_type = _detect_legacy_office_type(suffix, claimed)
        if legacy_type:
            return _build_resolved(
                LEGACY_EXTENSION_TO_TARGET[f".{legacy_type}"],
                suffix or f".{legacy_type}",
                needs_normalization=True,
                legacy_source_type=legacy_type,
            )

    if suffix == ".epub" or claimed == CANONICAL_TYPE_TO_MIME["epub"]:
        if _looks_like_epub(file_bytes):
            return _build_resolved("epub", suffix or ".epub")

    text_type = _detect_text_document_type(file_bytes, suffix, claimed)
    if text_type:
        source_extension = suffix or CANONICAL_TYPE_TO_EXTENSION[text_type]
        return _build_resolved(text_type, source_extension)

    if claimed in CANONICAL_MIME_TO_TYPE:
        canonical_type = CANONICAL_MIME_TO_TYPE[claimed]
        if canonical_type == "epub" and not _looks_like_epub(file_bytes):
            raise DocumentFormatError("无法解析 EPUB 文件")
        return _build_resolved(canonical_type, suffix or CANONICAL_TYPE_TO_EXTENSION[canonical_type])

    if claimed in LEGACY_MIME_TO_TARGET:
        legacy_type = {
            "application/msword": "doc",
            "application/vnd.ms-excel": "xls",
            "application/vnd.ms-powerpoint": "ppt",
        }[claimed]
        return _build_resolved(
            LEGACY_MIME_TO_TARGET[claimed],
            suffix or f".{legacy_type}",
            needs_normalization=True,
            legacy_source_type=legacy_type,
        )

    raise DocumentFormatError("不支持的文件类型")


def normalize_legacy_document(
    file_bytes: bytes,
    resolved: ResolvedDocumentFormat,
    filename: str | None = None,
) -> NormalizedDocument:
    """Normalize legacy Office documents into modern Office or PDF payloads."""
    if not resolved.needs_normalization or not resolved.legacy_source_type:
        return NormalizedDocument(
            content=file_bytes,
            filename=filename or f"document{resolved.storage_extension}",
            resolved_format=resolved,
            normalized=False,
        )

    source_name = filename or f"document{resolved.source_extension or resolved.storage_extension}"

    try:
        modern_bytes = _convert_with_libreoffice(
            file_bytes=file_bytes,
            source_extension=resolved.source_extension,
            target_extension=resolved.extension,
        )
    except LegacyDocumentNormalizationError as exc:
        logger.warning("Legacy Office conversion failed for %s: %s", source_name, exc)
        modern_bytes = None

    if modern_bytes is not None:
        normalized_name = f"{Path(source_name).stem}{resolved.extension}"
        return NormalizedDocument(
            content=modern_bytes,
            filename=normalized_name,
            resolved_format=_build_resolved(resolved.canonical_type, resolved.extension),
            normalized=True,
        )

    if resolved.legacy_source_type in {"doc", "ppt"}:
        pdf_bytes = _convert_with_libreoffice(
            file_bytes=file_bytes,
            source_extension=resolved.source_extension,
            target_extension=".pdf",
        )
        normalized_name = f"{Path(source_name).stem}.pdf"
        return NormalizedDocument(
            content=pdf_bytes,
            filename=normalized_name,
            resolved_format=_build_resolved("pdf", ".pdf"),
            normalized=True,
        )

    raise LegacyDocumentNormalizationError("结构化转换失败")


def find_office_binary() -> str | None:
    """Locate a LibreOffice executable."""
    for candidate in ("soffice", "libreoffice"):
        binary = shutil.which(candidate)
        if binary:
            return binary
    return None


def _build_resolved(
    canonical_type: str,
    source_extension: str,
    *,
    needs_normalization: bool = False,
    legacy_source_type: str | None = None,
) -> ResolvedDocumentFormat:
    source_extension = (source_extension or CANONICAL_TYPE_TO_EXTENSION[canonical_type]).lower()
    return ResolvedDocumentFormat(
        canonical_type=canonical_type,
        mime_type=CANONICAL_TYPE_TO_MIME[canonical_type],
        extension=CANONICAL_TYPE_TO_EXTENSION[canonical_type],
        source_extension=source_extension,
        parser_backend=canonical_type,
        needs_normalization=needs_normalization,
        legacy_source_type=legacy_source_type,
    )


def _detect_zip_document_type(file_bytes: bytes, suffix: str) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
            names = set(archive.namelist())
            if "mimetype" in names:
                try:
                    mimetype = archive.read("mimetype").decode("utf-8", errors="ignore").strip()
                except Exception:
                    mimetype = ""
                if mimetype == CANONICAL_TYPE_TO_MIME["epub"]:
                    return "epub"

            if any(name.startswith("word/") for name in names):
                return "docx"
            if any(name.startswith("xl/") for name in names):
                return "xlsx"
            if any(name.startswith("ppt/") for name in names):
                return "pptx"

            if suffix == ".epub" and {"META-INF/container.xml", "mimetype"} <= names:
                return "epub"
    except zipfile.BadZipFile:
        return None

    return None


def _detect_legacy_office_type(suffix: str, claimed_mime: str) -> str | None:
    if suffix in LEGACY_EXTENSION_TO_TARGET:
        return suffix.lstrip(".")
    if claimed_mime == "application/msword":
        return "doc"
    if claimed_mime == "application/vnd.ms-excel":
        return "xls"
    if claimed_mime == "application/vnd.ms-powerpoint":
        return "ppt"
    return None


def _detect_text_document_type(
    file_bytes: bytes,
    suffix: str,
    claimed_mime: str,
) -> str | None:
    text_type = TEXT_EXTENSION_TO_TYPE.get(suffix) or TEXT_MIME_TO_TYPE.get(claimed_mime)
    if suffix == ".epub" or claimed_mime == CANONICAL_TYPE_TO_MIME["epub"]:
        return None
    if text_type and _looks_like_text(file_bytes):
        return text_type
    if (
        not text_type
        and not suffix
        and claimed_mime in {"", "application/octet-stream", "text/plain"}
        and _looks_like_text(file_bytes)
    ):
        return "text"
    return None


def _looks_like_text(file_bytes: bytes) -> bool:
    sample = file_bytes[:8192]
    if not sample:
        return True
    if b"\x00" in sample:
        return False
    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"):
        try:
            decoded = sample.decode(encoding)
            printable = sum(
                1 for char in decoded if char.isprintable() or char in "\r\n\t"
            )
            if decoded and printable / len(decoded) >= 0.85:
                return True
        except UnicodeDecodeError:
            continue
    return False


def _looks_like_epub(file_bytes: bytes) -> bool:
    return _detect_zip_document_type(file_bytes, ".epub") == "epub"


def _convert_with_libreoffice(
    *,
    file_bytes: bytes,
    source_extension: str,
    target_extension: str,
) -> bytes:
    binary = find_office_binary()
    if not binary:
        raise LegacyDocumentNormalizationError("LibreOffice 未安装，无法转换旧版 Office 文档")

    tmp_dir = tempfile.mkdtemp(prefix="legacy_doc_")
    tmp_path = Path(tmp_dir)
    input_file = tmp_path / f"input{source_extension}"
    output_file = tmp_path / f"input{target_extension}"
    input_file.write_bytes(file_bytes)

    target_format = target_extension.lstrip(".")
    try:
        result = subprocess.run(
            [
                binary,
                "--headless",
                "--convert-to",
                target_format,
                "--outdir",
                str(tmp_path),
                str(input_file),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip() or result.stdout.strip()
            raise LegacyDocumentNormalizationError(stderr or "LibreOffice 转换失败")

        if not output_file.exists():
            raise LegacyDocumentNormalizationError("LibreOffice 未生成转换后的文件")

        return output_file.read_bytes()
    except subprocess.TimeoutExpired as exc:
        raise LegacyDocumentNormalizationError("LibreOffice 转换超时") from exc
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
