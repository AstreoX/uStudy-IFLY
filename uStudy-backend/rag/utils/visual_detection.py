"""快速检测文档是否包含视觉内容（图片/扫描页）。

用于在 VLM 增强阶段前快速判断是否需要处理，
纯文本文档可跳过整个增强流程，节省 API 成本和处理时间。
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)

# MIME types
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

# 扫描页检测阈值：页面文字少于此字符数视为潜在扫描页
SCAN_PAGE_TEXT_THRESHOLD = 20


def has_visual_content(content: bytes, mime_type: str) -> bool:
    """
    快速检测文档是否包含需要 VLM 处理的视觉内容。

    检测逻辑：
    - PDF：检测嵌入图片或扫描页（文字极少）
    - DOCX：检测嵌入图片
    - PPTX：总是返回 True（PPT 核心在视觉呈现）
    - 其他格式：返回 False

    Args:
        content: 文档二进制内容
        mime_type: 文档 MIME 类型

    Returns:
        True 如果文档包含视觉内容需要 VLM 处理
    """
    if mime_type == PDF_MIME:
        return _has_visual_content_pdf(content)
    elif mime_type == DOCX_MIME:
        return _has_visual_content_docx(content)
    elif mime_type == PPTX_MIME:
        # PPT 总是视觉优先，始终进行 VLM 处理
        return True
    else:
        # 其他格式（文本、Markdown、CSV 等）无视觉内容
        return False


def _has_visual_content_pdf(content: bytes) -> bool:
    """检测 PDF 是否包含图片或扫描页。"""
    try:
        import fitz
    except ImportError:
        logger.warning("PyMuPDF (fitz) 未安装，跳过 PDF 视觉检测")
        return True  # 保守策略：无法检测时默认处理

    try:
        doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
    except Exception as e:
        logger.warning("PDF 打开失败，跳过视觉检测: %s", e)
        return True  # 保守策略

    try:
        for page in doc:
            # 检测嵌入图片（full=False 更快，只返回图片数量）
            if page.get_images(full=False):
                return True

            # 扫描页检测：文字极少可能是扫描件
            page_text = page.get_text("text").strip()
            if len(page_text) < SCAN_PAGE_TEXT_THRESHOLD:
                return True

        return False
    finally:
        doc.close()


def _has_visual_content_docx(content: bytes) -> bool:
    """检测 DOCX 是否包含嵌入图片。"""
    try:
        from docx import Document
    except ImportError:
        logger.warning("python-docx 未安装，跳过 DOCX 视觉检测")
        return True  # 保守策略

    try:
        doc = Document(io.BytesIO(content))
    except Exception as e:
        logger.warning("DOCX 打开失败，跳过视觉检测: %s", e)
        return True  # 保守策略

    # 遍历文档关系，检测图片
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            return True

    return False
