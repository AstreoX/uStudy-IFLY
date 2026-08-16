"""从文档生成知识图谱 Agent（Map-Reduce 策略）"""

import asyncio
import io
import logging
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncGenerator, Callable
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.exceptions import (
    DocumentNotReadyError,
    LLMClientError,
    LLMParsingError,
    LLMParsingErrorWithOutput,
    SpaceNotFoundError,
)
from agents.graph_persistence import persist_graph
from agents.llm.client import OpenRouterClient
from agents.llm.prompts import (
    build_document_concept_extraction_prompt,
    build_document_knowledge_graph_prompt,
)
from agents.parsers.document_concepts import (
    ChunkExtractionResult,
    DocumentConceptParser,
)
from agents.parsers.knowledge_graph import KnowledgeGraphParser
from config import get_settings
from db.models import (
    DocumentChunk,
    DocumentProcessingTask,
    ProcessingStatus,
    SpaceDocument,
)

logger = logging.getLogger(__name__)

MAX_CONCEPTS = 200
MAX_RELATIONSHIPS = 500
# 直接从文件提取文本时，每段的目标字符数
SEGMENT_TARGET_CHARS = 1500
SEGMENT_MIN_CHARS = 200
SEGMENT_MAX_CHARS = 3000


@dataclass
class TextSegment:
    """从文件直接提取的文本段（兼容 DocumentChunk 接口）"""

    content: str
    chunk_index: int
    document_id: UUID | None = None


class DocumentKnowledgeGraphAgent:
    """从文档内容生成知识图谱的 Agent"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        settings = get_settings()
        self.llm_client = OpenRouterClient(
            model_override=settings.knowledge_graph_model or None,
        )
        self.kg_parser = KnowledgeGraphParser()
        self.concept_parser = DocumentConceptParser()
        self.settings = settings
        self.max_concurrent = settings.document_kg_max_concurrent_extractions
        self.max_chunks = settings.document_kg_max_chunks

    async def generate(
        self,
        user_id: UUID,
        space_id: UUID,
        document_ids: list[UUID],
        user_preference: str | None = None,
        on_progress: Callable[..., Any] | None = None,
    ) -> tuple[UUID, int, int]:
        """
        从文档生成知识图谱并持久化

        Args:
            user_id: 用户 ID
            space_id: 学习空间 ID
            document_ids: 文档 ID 列表
            user_preference: 用户偏好（可选）
            on_progress: 进度回调

        Returns:
            (space_id, node_count, edge_count)
        """
        # 1. 验证 space 访问权限
        await self._verify_space(space_id, user_id)

        # 2. 验证文档并获取 chunks
        documents, chunks = await self._load_document_chunks(space_id, document_ids)
        document_titles = [doc.title for doc in documents]

        total_chunks = len(chunks)
        logger.info(
            "文档知识图谱生成: space_id=%s, documents=%d, chunks=%d",
            space_id,
            len(documents),
            total_chunks,
        )

        # 3. Phase 1: Map — 并发提取概念
        extraction_results = await self._phase1_extract_concepts(
            chunks=chunks,
            document_title_map={doc.id: doc.title for doc in documents},
            on_progress=on_progress,
        )

        # 4. 汇总去重
        concept_summary, relationship_summary = self._aggregate_results(
            extraction_results
        )

        if not concept_summary.strip():
            raise LLMParsingError("文档中未提取到任何有效概念")

        # 5. Phase 2: Reduce — 合并生成知识图谱
        llm_output = await self._phase2_consolidate(
            document_titles=document_titles,
            concept_summary=concept_summary,
            relationship_summary=relationship_summary,
            user_preference=user_preference,
        )

        # 6. 解析
        root_label = document_titles[0] if len(document_titles) == 1 else None
        parsed_graph = self.kg_parser.parse(llm_output, root_label=root_label)

        # 7. 持久化（使用共享工具函数）
        node_count, edge_count = await persist_graph(self.db, space_id, parsed_graph)

        logger.info(
            "文档知识图谱生成完成: space_id=%s, nodes=%d, edges=%d",
            space_id,
            node_count,
            edge_count,
        )

        return space_id, node_count, edge_count

    async def _verify_space(self, space_id: UUID, user_id: UUID) -> None:
        """验证学习空间存在且用户有权访问"""
        from spaces.authorization import verify_space_access as _verify
        from spaces.authorization import (
            SpaceAccessDeniedError as _AccessDenied,
            SpaceNotFoundError as _NotFound,
        )

        try:
            await _verify(self.db, space_id, user_id)
        except (_NotFound, _AccessDenied):
            raise SpaceNotFoundError(f"学习空间不存在或无权访问: {space_id}")

    async def _load_document_chunks(
        self,
        space_id: UUID,
        document_ids: list[UUID],
    ) -> tuple[list[SpaceDocument], list]:
        """
        加载文档内容用于 KG 生成。

        优先从已处理的 DocumentChunk 加载；如果 RAG 未完成，
        直接从上传文件提取文本段（不等待向量化）。

        Returns:
            (documents, chunks_or_segments)
        """
        # 验证文档属于该 space
        result = await self.db.execute(
            select(SpaceDocument).where(
                SpaceDocument.id.in_(document_ids),
                SpaceDocument.space_id == space_id,
            )
        )
        documents = list(result.scalars().all())

        found_ids = {doc.id for doc in documents}
        missing_ids = set(document_ids) - found_ids
        if missing_ids:
            raise ValueError(
                f"以下文档不存在或不属于该学习空间: {missing_ids}"
            )

        # 尝试加载已有 chunks（RAG 已完成的情况）
        result = await self.db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id.in_(document_ids))
            .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        )
        chunks = list(result.scalars().all())

        if chunks:
            logger.info("使用已处理的 %d 个 chunks", len(chunks))
            # 限制 chunk 数量
            if len(chunks) > self.max_chunks:
                logger.warning(
                    "Chunk 数量 %d 超过限制 %d，进行均匀采样",
                    len(chunks),
                    self.max_chunks,
                )
                step = len(chunks) / self.max_chunks
                chunks = [chunks[int(i * step)] for i in range(self.max_chunks)]
            return documents, chunks

        # RAG 未完成：直接从上传文件提取文本段
        logger.info("RAG 未完成，直接从文件提取文本段")
        all_segments: list[TextSegment] = []
        for doc in documents:
            segments = await self._load_text_segments_from_file(doc)
            all_segments.extend(segments)

        if not all_segments:
            raise ValueError("文档中没有可用的文本内容")

        # 限制段数量
        if len(all_segments) > self.max_chunks:
            step = len(all_segments) / self.max_chunks
            all_segments = [all_segments[int(i * step)] for i in range(self.max_chunks)]

        logger.info("从文件提取了 %d 个文本段", len(all_segments))
        return documents, all_segments

    async def _load_text_segments_from_file(
        self, document: SpaceDocument
    ) -> list[TextSegment]:
        """
        直接从上传的文件提取文本段，不依赖 RAG 处理完成。

        支持 PDF 格式（主要场景），其他格式尝试纯文本读取。
        """
        settings = get_settings()
        # document.url 格式: /uploads/documents/xxx.pdf
        relative_path = document.url.lstrip("/uploads/")
        file_path = Path(settings.upload_dir) / relative_path

        if not file_path.exists():
            logger.warning("文件不存在: %s", file_path)
            return []

        file_ext = file_path.suffix.lower()
        content = await asyncio.to_thread(file_path.read_bytes)

        if file_ext == ".pdf":
            return await self._extract_pdf_segments(content, document.id)
        else:
            # 其他格式：尝试纯文本
            try:
                text = content.decode("utf-8", errors="ignore")
            except Exception:
                logger.warning("无法读取文件文本: %s", file_path)
                return []
            return self._split_text_into_segments(text, document.id)

    async def _extract_pdf_segments(
        self, content: bytes, document_id: UUID
    ) -> list[TextSegment]:
        """从 PDF 按页提取文本，然后归一化为合适大小的段"""
        import fitz  # PyMuPDF

        def _extract():
            doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
            page_texts = []
            for page_num in range(len(doc)):
                text = doc[page_num].get_text("text").strip()
                if text and len(text) > 30:
                    page_texts.append(text)
            doc.close()
            return page_texts

        page_texts = await asyncio.to_thread(_extract)

        if not page_texts:
            return []

        # 合并所有页面文本，然后按目标大小分段
        full_text = "\n\n".join(page_texts)
        return self._split_text_into_segments(full_text, document_id)

    def _split_text_into_segments(
        self, text: str, document_id: UUID
    ) -> list[TextSegment]:
        """将长文本按段落边界拆分为合适大小的段"""
        if not text.strip():
            return []

        # 按段落分割
        paragraphs = text.split("\n\n")
        segments: list[TextSegment] = []
        current_buf = ""
        seg_idx = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_buf) + len(para) + 2 > SEGMENT_MAX_CHARS and current_buf:
                # 当前缓冲区已满，输出为一个段
                if len(current_buf) >= SEGMENT_MIN_CHARS:
                    segments.append(TextSegment(
                        content=current_buf,
                        chunk_index=seg_idx,
                        document_id=document_id,
                    ))
                    seg_idx += 1
                current_buf = para
            else:
                current_buf = current_buf + "\n\n" + para if current_buf else para

        # 最后的缓冲区
        if current_buf and len(current_buf) >= SEGMENT_MIN_CHARS:
            segments.append(TextSegment(
                content=current_buf,
                chunk_index=seg_idx,
                document_id=document_id,
            ))

        return segments

    async def _phase1_extract_concepts(
        self,
        chunks: list[DocumentChunk],
        document_title_map: dict[UUID, str],
        on_progress: Callable[..., Any] | None = None,
    ) -> list[ChunkExtractionResult]:
        """
        Phase 1 (Map): 并发对每个 chunk 提取概念

        使用 semaphore 限制并发数，失败的 chunk 跳过
        """
        semaphore = asyncio.Semaphore(self.max_concurrent)
        total = len(chunks)
        # 使用 Lock 保护 completed_count 的原子递增
        progress_lock = asyncio.Lock()
        completed_count = 0

        async def extract_one(chunk: DocumentChunk) -> ChunkExtractionResult | None:
            nonlocal completed_count

            async with semaphore:
                try:
                    doc_title = document_title_map.get(chunk.document_id, "未知文档")
                    messages = build_document_concept_extraction_prompt(
                        chunk_content=chunk.content,
                        document_title=doc_title,
                        chunk_index=chunk.chunk_index,
                    )
                    llm_output = await self.llm_client.complete(messages)
                    result = self.concept_parser.parse(llm_output)
                    return result
                except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
                    logger.warning(
                        "Chunk %d 概念提取 LLM 调用失败: %s",
                        chunk.chunk_index,
                        e,
                    )
                    return None
                except Exception as e:
                    logger.warning(
                        "Chunk %d 概念提取失败: %s",
                        chunk.chunk_index,
                        e,
                    )
                    return None

            # 在 semaphore 外更新进度
            async with progress_lock:
                completed_count += 1
                current = completed_count

            if on_progress and current % 5 == 0:
                await on_progress(
                    {"phase": "extraction", "completed": current, "total": total}
                )

        tasks = [extract_one(chunk) for chunk in chunks]
        task_results = await asyncio.gather(*tasks)

        results = [r for r in task_results if r and (r.concepts or r.relationships)]

        success_count = len(results)
        logger.info(
            "Phase 1 完成: %d/%d chunks 成功提取概念",
            success_count,
            total,
        )

        if success_count == 0:
            raise LLMParsingError("所有 chunk 的概念提取均失败")

        return results

    def _aggregate_results(
        self,
        results: list[ChunkExtractionResult],
    ) -> tuple[str, str]:
        """
        汇总所有 chunk 的提取结果，去重并格式化

        Returns:
            (concept_summary_text, relationship_summary_text)
        """
        # 统计概念出现频率（大小写不敏感去重）
        concept_counter: Counter[str] = Counter()
        # normalized_key -> 首次出现的原始名称
        concept_display_name: dict[str, str] = {}

        for r in results:
            for c in r.concepts:
                normalized = c.name.strip().lower()
                concept_counter[normalized] += 1
                if normalized not in concept_display_name:
                    concept_display_name[normalized] = c.name

        # 取频率最高的 top N
        top_concepts = concept_counter.most_common(MAX_CONCEPTS)

        concept_lines = []
        for normalized, count in top_concepts:
            display_name = concept_display_name[normalized]
            if count > 1:
                concept_lines.append(f"- {display_name} (出现 {count} 次)")
            else:
                concept_lines.append(f"- {display_name}")

        concept_summary = "\n".join(concept_lines)

        # 汇总关系（去重，加上限）
        seen_relations: set[tuple[str, str, str]] = set()
        relationship_lines: list[str] = []

        for r in results:
            for rel in r.relationships:
                if len(seen_relations) >= MAX_RELATIONSHIPS:
                    break
                key = (rel.source.lower(), rel.target.lower(), rel.relation_type)
                if key not in seen_relations:
                    seen_relations.add(key)
                    relationship_lines.append(
                        f"{rel.source} -> {rel.target}: {rel.relation_type}"
                    )

        relationship_summary = "\n".join(relationship_lines) if relationship_lines else "无"

        logger.info(
            "概念汇总: %d 个唯一概念, %d 条唯一关系",
            len(top_concepts),
            len(seen_relations),
        )

        return concept_summary, relationship_summary

    async def _phase2_consolidate(
        self,
        document_titles: list[str],
        concept_summary: str,
        relationship_summary: str,
        user_preference: str | None,
    ) -> str:
        """
        Phase 2 (Reduce): 调用 LLM 将概念合并为知识图谱

        带重试。仅验证 LLM 输出可解析，返回原始字符串供调用方解析（带 root_label）。
        """
        messages = build_document_knowledge_graph_prompt(
            document_titles=document_titles,
            concept_summary=concept_summary,
            relationship_summary=relationship_summary,
            user_preference=user_preference,
        )

        max_retries = self.settings.llm_max_retries
        last_error: Exception | None = None
        last_llm_output: str | None = None

        for attempt in range(max_retries):
            try:
                logger.info("Phase 2 LLM 调用尝试 %d/%d", attempt + 1, max_retries)
                llm_output = await self.llm_client.complete(messages)
                last_llm_output = llm_output

                # 验证可以解析（不传 root_label，仅做格式校验）
                self.kg_parser.parse(llm_output)
                return llm_output

            except LLMParsingError as e:
                logger.warning(
                    "Phase 2 LLM 输出解析失败 (尝试 %d/%d): %s",
                    attempt + 1,
                    max_retries,
                    e,
                )
                last_error = e
                continue
            except (httpx.HTTPStatusError, httpx.TimeoutException) as e:
                logger.warning("Phase 2 LLM API 调用失败: %s", e)
                last_error = LLMClientError(str(e))
                continue

        # 所有重试都失败
        if last_llm_output and isinstance(last_error, LLMParsingError):
            raise LLMParsingErrorWithOutput(str(last_error), llm_output=last_llm_output)
        raise last_error or LLMClientError("Phase 2 LLM 调用失败")

    # ===== 流式生成（SSE 场景） =====

    async def _extract_one_chunk(
        self,
        chunk: DocumentChunk,
        doc_title: str,
    ) -> ChunkExtractionResult | None:
        """对单个 chunk 提取概念（用于流式顺序调用）"""
        try:
            messages = build_document_concept_extraction_prompt(
                chunk_content=chunk.content,
                document_title=doc_title,
                chunk_index=chunk.chunk_index,
            )
            llm_output = await self.llm_client.complete(messages)
            return self.concept_parser.parse(llm_output)
        except Exception as e:
            logger.warning("Chunk %d 概念提取失败: %s", chunk.chunk_index, e)
            return None

    async def stream_generate(
        self,
        user_id: UUID,
        space_id: UUID,
        document_ids: list[UUID],
        user_preference: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """
        流式生成知识图谱，yield SSE 事件字典

        Phase 1 顺序执行（逐个汇报进度），Phase 2 流式生成 XML
        """
        # 1. 验证
        await self._verify_space(space_id, user_id)
        documents, chunks = await self._load_document_chunks(space_id, document_ids)
        document_titles = [doc.title for doc in documents]
        doc_title_map = {doc.id: doc.title for doc in documents}

        total_chunks = len(chunks)
        logger.info(
            "流式文档知识图谱生成: space_id=%s, docs=%d, chunks=%d",
            space_id, len(documents), total_chunks,
        )

        # 2. Phase 1: 顺序提取概念
        yield {"event": "phase", "data": {"phase": "extraction", "total_chunks": total_chunks}}

        all_results: list[ChunkExtractionResult] = []
        for i, chunk in enumerate(chunks):
            doc_title = doc_title_map.get(chunk.document_id, "未知文档")
            result = await self._extract_one_chunk(chunk, doc_title)
            if result and (result.concepts or result.relationships):
                all_results.append(result)
            yield {"event": "progress", "data": {"completed": i + 1, "total": total_chunks}}

        if not all_results:
            yield {"event": "error", "data": {"message": "文档中未提取到有效概念"}}
            return

        # 3. 汇总
        concept_summary, relationship_summary = self._aggregate_results(all_results)

        # 4. Phase 2: 流式生成知识图谱
        yield {"event": "phase", "data": {"phase": "consolidation"}}

        messages = build_document_knowledge_graph_prompt(
            document_titles=document_titles,
            concept_summary=concept_summary,
            relationship_summary=relationship_summary,
            user_preference=user_preference,
        )

        full_output = ""
        # 跟踪已发送的行数，避免重复发送节点/边
        last_processed_line_count = 0
        # 跟踪层级栈，为节点确定 parent
        parent_stack: list[str] = []
        # 标记是否进入 /advanced_knowledge_connections 区域
        in_advanced_section = False

        async for text_delta in self.llm_client.stream_complete(messages):
            full_output += text_delta
            yield {"event": "kg_delta", "data": {"content": text_delta}}

            # 尝试从已完成的行中解析节点和边
            lines = full_output.split("\n")
            # 最后一行可能不完整，不处理
            complete_lines = lines[:-1] if not full_output.endswith("\n") else lines

            for line_idx in range(last_processed_line_count, len(complete_lines)):
                line = complete_lines[line_idx]
                stripped = line.strip()

                # 检查 section 切换
                if stripped.startswith("/advanced_knowledge_connections"):
                    in_advanced_section = True
                    continue
                if stripped.startswith("/basic_knowledge_tree"):
                    in_advanced_section = False
                    continue

                if not in_advanced_section:
                    # 尝试解析节点
                    node_data = KnowledgeGraphParser.parse_incremental_node(stripped)
                    if node_data:
                        level = node_data["level"]
                        label = node_data["label"]
                        # 确定 parent
                        parent = None
                        if level > 1 and len(parent_stack) >= level - 1:
                            parent = parent_stack[level - 2]
                        # 更新栈
                        while len(parent_stack) >= level:
                            parent_stack.pop()
                        parent_stack.append(label)
                        yield {
                            "event": "kg_node",
                            "data": {"label": label, "level": level, "parent": parent},
                        }
                else:
                    # 尝试解析边
                    edge_data = KnowledgeGraphParser.parse_incremental_edge(stripped)
                    if edge_data:
                        yield {"event": "kg_edge", "data": edge_data}

            last_processed_line_count = len(complete_lines)

        # 5. 最终完整解析 + 持久化
        try:
            root_label = document_titles[0] if len(document_titles) == 1 else None
            parsed_graph = self.kg_parser.parse(full_output, root_label=root_label)
            node_count, edge_count = await persist_graph(self.db, space_id, parsed_graph)

            logger.info(
                "流式文档知识图谱生成完成: space_id=%s, nodes=%d, edges=%d",
                space_id, node_count, edge_count,
            )
            yield {
                "event": "done",
                "data": {"node_count": node_count, "edge_count": edge_count},
            }
        except Exception as e:
            logger.error("知识图谱持久化失败: %s", e)
            yield {"event": "error", "data": {"message": f"图谱保存失败: {e}"}}
