"""File validation and image processing utilities"""

import io
import logging
import re
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

# Prevent decompression bomb attacks
Image.MAX_IMAGE_PIXELS = 50_000_000  # ~50 megapixels

logger = logging.getLogger(__name__)

# File size limit: 10MB
MAX_FILE_SIZE = 10 * 1024 * 1024

# Magic bytes for file type detection
MAGIC_BYTES = {
    # Images
    b"\xFF\xD8\xFF": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",  # Needs additional check for WEBP
    # Documents
    b"%PDF": "application/pdf",
    b"PK\x03\x04": "application/zip",  # Also DOCX, XLSX, PPTX
}

# Allowed MIME types
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

ALLOWED_FILE_TYPES = {
    "application/pdf",
    "application/msword",  # .doc
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.ms-excel",  # .xls
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "application/vnd.ms-powerpoint",  # .ppt
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
    "text/plain",
}

# Image processing settings
MAX_IMAGE_WIDTH = 1920
MAX_IMAGE_HEIGHT = 1920
THUMBNAIL_SIZE = (300, 300)
WEBP_QUALITY = 85


class FileValidationError(Exception):
    """Raised when file validation fails"""

    pass


def detect_file_type(file_data: bytes) -> str:
    """
    Detect file type using magic bytes.

    Args:
        file_data: File binary data

    Returns:
        MIME type string

    Raises:
        FileValidationError: If file type cannot be detected
    """
    for magic, mime_type in MAGIC_BYTES.items():
        if file_data.startswith(magic):
            # Special handling for WebP
            if magic == b"RIFF":
                if len(file_data) >= 12 and file_data[8:12] == b"WEBP":
                    return "image/webp"
                # Not a WebP RIFF file, skip this match
                continue
            # Special handling for Office files (all start with PK\x03\x04)
            if magic == b"PK\x03\x04":
                # Try to read as zip and check for office file markers
                try:
                    # This is a simplified check - real implementation would inspect zip contents
                    if b"word/" in file_data[:1000]:
                        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    elif b"xl/" in file_data[:1000]:
                        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    elif b"ppt/" in file_data[:1000]:
                        return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
                except Exception:
                    pass
            return mime_type

    raise FileValidationError("无法识别的文件类型")


def validate_file_size(file_data: bytes) -> None:
    """
    Validate file size.

    Args:
        file_data: File binary data

    Raises:
        FileValidationError: If file size exceeds limit
    """
    file_size = len(file_data)
    if file_size > MAX_FILE_SIZE:
        raise FileValidationError(
            f"文件大小超过限制 (最大 {MAX_FILE_SIZE / 1024 / 1024:.0f}MB)"
        )


def validate_file_type(mime_type: str, is_image: bool) -> None:
    """
    Validate file MIME type against whitelist.

    Args:
        mime_type: MIME type string
        is_image: Whether file should be an image

    Raises:
        FileValidationError: If file type is not allowed
    """
    if is_image:
        if mime_type not in ALLOWED_IMAGE_TYPES:
            raise FileValidationError(
                f"不支持的图片格式 (支持: JPEG, PNG, WebP, GIF)"
            )
    else:
        if mime_type not in ALLOWED_FILE_TYPES:
            raise FileValidationError(
                f"不支持的文件格式 (支持: PDF, Word, Excel, PowerPoint, TXT)"
            )


def compress_image(
    image_data: bytes, max_width: int = MAX_IMAGE_WIDTH, max_height: int = MAX_IMAGE_HEIGHT
) -> Tuple[bytes, int, int]:
    """
    Compress image to WebP format and resize if necessary.

    Args:
        image_data: Original image binary data
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels

    Returns:
        Tuple of (compressed_data, width, height)

    Raises:
        FileValidationError: If image processing fails
    """
    try:
        # Open image
        image = Image.open(io.BytesIO(image_data))

        # Convert RGBA to RGB if necessary (WebP supports both, but RGB is smaller)
        if image.mode == "RGBA":
            # Create white background
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])  # 3 is the alpha channel
            image = background
        elif image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        # Get original dimensions
        original_width, original_height = image.size

        # Resize if too large
        if original_width > max_width or original_height > max_height:
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        # Get final dimensions
        width, height = image.size

        # Save as WebP
        output = io.BytesIO()
        image.save(output, format="WEBP", quality=WEBP_QUALITY, method=6)
        compressed_data = output.getvalue()

        logger.info(
            f"Compressed image from {len(image_data)} to {len(compressed_data)} bytes "
            f"({original_width}x{original_height} -> {width}x{height})"
        )

        return compressed_data, width, height

    except Exception as e:
        logger.error(f"Image compression failed: {e}", exc_info=True)
        raise FileValidationError(f"图片处理失败: {str(e)}")


def generate_thumbnail(image_data: bytes) -> bytes:
    """
    Generate thumbnail for image.

    Args:
        image_data: Original image binary data

    Returns:
        Thumbnail image data in WebP format

    Raises:
        FileValidationError: If thumbnail generation fails
    """
    try:
        # Open image
        image = Image.open(io.BytesIO(image_data))

        # Convert to RGB
        if image.mode == "RGBA":
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3])
            image = background
        elif image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        # Create thumbnail
        image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

        # Save as WebP
        output = io.BytesIO()
        image.save(output, format="WEBP", quality=WEBP_QUALITY, method=6)
        thumbnail_data = output.getvalue()

        logger.info(
            f"Generated thumbnail: {image.size[0]}x{image.size[1]}, "
            f"{len(thumbnail_data)} bytes"
        )

        return thumbnail_data

    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}", exc_info=True)
        raise FileValidationError(f"缩略图生成失败: {str(e)}")


def get_file_extension(mime_type: str) -> str:
    """
    Get file extension from MIME type.

    Args:
        mime_type: MIME type string

    Returns:
        File extension (e.g., "webp", "pdf")
    """
    mime_to_ext = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/webp": "webp",
        "application/pdf": "pdf",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/vnd.ms-excel": "xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "application/vnd.ms-powerpoint": "ppt",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
        "text/plain": "txt",
    }
    return mime_to_ext.get(mime_type, "bin")


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    Sanitize filename to prevent security issues.

    Args:
        filename: Original filename from user
        max_length: Maximum allowed length

    Returns:
        Sanitized filename safe for storage
    """
    if not filename:
        return "unnamed"

    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Remove non-printable and potentially dangerous characters
    # Allow ASCII printable, Chinese, Japanese, Korean characters
    filename = re.sub(
        r'[^\x20-\x7E\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]+', '_', filename
    )

    # Truncate to max length
    filename = filename[:max_length] if len(filename) > max_length else filename

    # Ensure not empty after sanitization
    return filename if filename.strip() else "unnamed"
