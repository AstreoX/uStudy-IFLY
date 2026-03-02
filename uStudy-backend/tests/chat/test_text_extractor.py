"""Tests for text extraction from file attachments"""

import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from chat.text_extractor import extract_text_from_attachment, _truncate_by_tokens
from db.models import MessageAttachment, AttachmentType
from rag.chunking import get_chunker


@pytest.fixture
def mock_attachment():
    """Create a mock MessageAttachment object"""
    attachment = Mock(spec=MessageAttachment)
    attachment.attachment_type = AttachmentType.FILE
    attachment.file_url = "/uploads/attachments/files/test.pdf"
    attachment.original_filename = "test.pdf"
    attachment.mime_type = "application/pdf"
    attachment.extracted_text = None
    attachment.extraction_metadata = None
    return attachment


@pytest.fixture
def sample_pdf_content():
    """Sample PDF content (bytes)"""
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n%%EOF"


@pytest.mark.asyncio
async def test_extract_text_from_attachment_image_type():
    """Test that extraction returns None for image attachments"""
    attachment = Mock(spec=MessageAttachment)
    attachment.attachment_type = AttachmentType.IMAGE

    extracted_text, metadata = await extract_text_from_attachment(attachment)

    assert extracted_text is None
    assert metadata["token_count"] == 0
    assert metadata["extraction_error"] is None


@pytest.mark.asyncio
async def test_extract_text_timeout():
    """Test that extraction times out after configured seconds"""
    attachment = Mock(spec=MessageAttachment)
    attachment.attachment_type = AttachmentType.FILE
    attachment.file_url = "/uploads/attachments/files/test.pdf"
    attachment.original_filename = "test.pdf"
    attachment.mime_type = "application/pdf"

    with patch("chat.text_extractor.asyncio.wait_for") as mock_wait_for:
        # Simulate timeout
        import asyncio

        mock_wait_for.side_effect = asyncio.TimeoutError()

        extracted_text, metadata = await extract_text_from_attachment(attachment)

        assert extracted_text is None
        assert "timeout" in metadata["extraction_error"].lower()


@pytest.mark.asyncio
async def test_extract_text_unsupported_format():
    """Test that unsupported file types are handled gracefully"""
    attachment = Mock(spec=MessageAttachment)
    attachment.attachment_type = AttachmentType.FILE
    attachment.file_url = "/uploads/attachments/files/test.xyz"
    attachment.original_filename = "test.xyz"
    attachment.mime_type = "application/xyz"

    with patch("chat.text_extractor._read_file") as mock_read:
        mock_read.return_value = b"some content"

        extracted_text, metadata = await extract_text_from_attachment(attachment)

        assert extracted_text is None
        assert "不支持的文件类型" in metadata["extraction_error"]


@pytest.mark.asyncio
async def test_extract_text_file_not_found():
    """Test that missing files are handled gracefully"""
    attachment = Mock(spec=MessageAttachment)
    attachment.attachment_type = AttachmentType.FILE
    attachment.file_url = "/uploads/attachments/files/nonexistent.pdf"
    attachment.original_filename = "nonexistent.pdf"
    attachment.mime_type = "application/pdf"

    extracted_text, metadata = await extract_text_from_attachment(attachment)

    assert extracted_text is None
    assert "File not found" in metadata["extraction_error"]


def test_truncate_by_tokens():
    """Test token-based truncation"""
    chunker = get_chunker("text/plain")

    # Create a long text
    long_text = "Hello world. " * 1000  # Approximately 2000 tokens

    # Truncate to 100 tokens
    truncated = _truncate_by_tokens(long_text, 100, chunker)

    # Verify truncation
    truncated_tokens = chunker.count_tokens(truncated)
    assert truncated_tokens <= 100 + 20  # Allow some margin for truncation notice

    # Verify truncation notice is added
    assert "Content truncated" in truncated


def test_truncate_by_tokens_no_truncation():
    """Test that short text is not truncated"""
    chunker = get_chunker("text/plain")

    short_text = "Hello world."
    truncated = _truncate_by_tokens(short_text, 1000, chunker)

    # Should be unchanged
    assert truncated == short_text
    assert "Content truncated" not in truncated


@pytest.mark.asyncio
async def test_extract_text_success_metadata():
    """Test that successful extraction includes correct metadata"""
    attachment = Mock(spec=MessageAttachment)
    attachment.attachment_type = AttachmentType.FILE
    attachment.file_url = "/uploads/attachments/files/test.txt"
    attachment.original_filename = "test.txt"
    attachment.mime_type = "text/plain"

    # Use longer text to ensure it meets min_size token requirement (50 tokens)
    test_content = " ".join(["This is a test document with enough content."] * 20)

    with patch("chat.text_extractor._read_file") as mock_read:
        # Mock file reading
        mock_read.return_value = test_content.encode("utf-8")

        with patch("chat.text_extractor.Path"):
            # Mock file path existence
            extracted_text, metadata = await extract_text_from_attachment(attachment)

            # Verify extraction success
            assert extracted_text is not None
            assert "test document" in extracted_text

            # Verify metadata
            assert "extracted_at" in metadata
            assert metadata["token_count"] > 0
            assert metadata["truncated"] is False
            assert metadata["extraction_error"] is None


# Integration test placeholder
@pytest.mark.skip(reason="Requires database and real file system setup")
@pytest.mark.asyncio
async def test_extract_text_integration():
    """
    Integration test for text extraction with real files.

    This test should:
    1. Create a real PDF/DOCX/TXT file
    2. Create a MessageAttachment record
    3. Extract text
    4. Verify extraction
    5. Verify caching
    """
    pass
