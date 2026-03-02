"""文本提取工具，复用 RAG 解析器提取文件附件内容"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from config import get_settings
from rag.chunking import get_chunker
from db.models import MessageAttachment, AttachmentType

logger = logging.getLogger(__name__)


async def extract_text_from_attachment(
    attachment: MessageAttachment,
) -> Tuple[Optional[str], dict]:
    """
    从文件附件提取文本内容。

    Args:
        attachment: MessageAttachment 对象

    Returns:
        (extracted_text, metadata) 元组
        - extracted_text: 提取的文本，失败时为 None
        - metadata: 提取元数据字典 {
            "extracted_at": "ISO timestamp",
            "token_count": int,
            "truncated": bool,
            "extraction_error": str | None
          }
    """
    settings = get_settings()
    metadata = {
        "extracted_at": datetime.utcnow().isoformat(),
        "token_count": 0,
        "truncated": False,
        "extraction_error": None,
    }

    # 只处理文件类型附件
    if attachment.attachment_type != AttachmentType.FILE:
        return None, metadata

    try:
        # 1. 读取文件（从 file_url 提取路径）
        # file_url 格式: /uploads/attachments/xxx.pdf
        url_path = attachment.file_url.split("/uploads/")[-1]
        file_path = Path(settings.upload_dir) / url_path

        logger.info(f"Extracting text from file: {file_path}")

        # 2. 异步读取文件内容
        file_data = await asyncio.wait_for(
            asyncio.to_thread(_read_file, file_path),
            timeout=settings.attachment_text_timeout_seconds,
        )

        # 3. 获取对应的 chunker
        chunker = get_chunker(attachment.mime_type)

        # 4. 提取文本块（在线程中执行）
        chunks = await asyncio.wait_for(
            asyncio.to_thread(chunker.chunk, file_data, attachment.original_filename),
            timeout=settings.attachment_text_timeout_seconds,
        )

        # 5. 合并所有 chunk 的内容
        full_text = "\n\n".join(chunk.content for chunk in chunks)

        # 6. Token 计数和截断
        token_count = chunker.count_tokens(full_text)
        metadata["token_count"] = token_count

        logger.info(
            f"Extracted {token_count} tokens from {attachment.original_filename}"
        )

        if token_count > settings.attachment_text_max_tokens:
            truncated_text = _truncate_by_tokens(
                full_text, settings.attachment_text_max_tokens, chunker
            )
            metadata["truncated"] = True
            logger.warning(
                f"Text truncated from {token_count} to {settings.attachment_text_max_tokens} tokens"
            )
            return truncated_text, metadata

        return full_text, metadata

    except asyncio.TimeoutError:
        error_msg = (
            f"Text extraction timeout after {settings.attachment_text_timeout_seconds}s"
        )
        logger.warning(f"{error_msg} for file: {attachment.original_filename}")
        metadata["extraction_error"] = error_msg
        return None, metadata

    except ValueError as e:
        # 不支持的文件类型
        error_msg = str(e)
        logger.warning(f"Unsupported file type: {error_msg}")
        metadata["extraction_error"] = error_msg
        return None, metadata

    except FileNotFoundError as e:
        error_msg = f"File not found: {str(e)}"
        logger.error(f"{error_msg} for file: {attachment.original_filename}")
        metadata["extraction_error"] = error_msg
        return None, metadata

    except Exception as e:
        error_msg = f"Extraction failed: {str(e)}"
        logger.error(
            f"{error_msg} for file: {attachment.original_filename}", exc_info=True
        )
        metadata["extraction_error"] = error_msg
        return None, metadata


def _read_file(file_path: Path) -> bytes:
    """同步读取文件（在线程中调用）"""
    with open(file_path, "rb") as f:
        return f.read()


def _truncate_by_tokens(text: str, max_tokens: int, chunker) -> str:
    """
    按 token 数截断文本

    Args:
        text: 原始文本
        max_tokens: 最大 token 数
        chunker: 用于 token 计数的 chunker 实例

    Returns:
        截断后的文本（带截断提示）
    """
    tokens = chunker._tokenizer.encode(text)
    if len(tokens) <= max_tokens:
        return text

    # 截断 tokens
    truncated_tokens = tokens[:max_tokens]
    truncated_text = chunker._tokenizer.decode(truncated_tokens)

    # 添加截断提示
    original_count = len(tokens)
    notice = f"\n\n[Content truncated: showing first {max_tokens} tokens of {original_count}]"

    return truncated_text + notice
