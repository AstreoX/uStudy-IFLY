"""文档概念提取结果解析器"""

import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ExtractedConcept:
    """从文档 chunk 中提取的概念"""

    name: str


@dataclass
class ExtractedRelationship:
    """从文档 chunk 中提取的关系"""

    source: str
    target: str
    relation_type: str  # prerequisite / contains / related


@dataclass
class ChunkExtractionResult:
    """单个 chunk 的概念提取结果"""

    concepts: list[ExtractedConcept] = field(default_factory=list)
    relationships: list[ExtractedRelationship] = field(default_factory=list)


# 合法的关系类型
VALID_RELATION_TYPES = {"prerequisite", "contains", "related"}


class DocumentConceptParser:
    """文档概念提取结果解析器"""

    CONCEPTS_PATTERN = re.compile(
        r"<concepts>(.*?)</concepts>",
        re.DOTALL,
    )
    RELATIONSHIPS_PATTERN = re.compile(
        r"<relationships>(.*?)</relationships>",
        re.DOTALL,
    )
    # 概念行: - 概念名称
    CONCEPT_LINE_PATTERN = re.compile(
        r"^\s*[-*]\s+(.+?)\s*$",
        re.MULTILINE,
    )
    # 关系行: 概念A -> 概念B: type
    RELATIONSHIP_LINE_PATTERN = re.compile(
        r"^\s*(.+?)\s*->\s*(.+?)\s*:\s*(\w+)\s*$",
        re.MULTILINE,
    )

    def parse(self, llm_output: str) -> ChunkExtractionResult:
        """
        解析 Phase 1 LLM 输出，提取概念和关系

        容错设计：解析失败返回空结果而非抛异常
        """
        concepts = self._parse_concepts(llm_output)
        relationships = self._parse_relationships(llm_output)
        return ChunkExtractionResult(concepts=concepts, relationships=relationships)

    def _parse_concepts(self, output: str) -> list[ExtractedConcept]:
        """解析 <concepts> 块"""
        match = self.CONCEPTS_PATTERN.search(output)
        if not match:
            logger.debug("未找到 <concepts> 标签")
            return []

        content = match.group(1).strip()
        if not content:
            return []

        concepts = []
        for line_match in self.CONCEPT_LINE_PATTERN.finditer(content):
            name = line_match.group(1).strip()
            if name and len(name) <= 50:
                concepts.append(ExtractedConcept(name=name))

        return concepts

    def _parse_relationships(self, output: str) -> list[ExtractedRelationship]:
        """解析 <relationships> 块"""
        match = self.RELATIONSHIPS_PATTERN.search(output)
        if not match:
            logger.debug("未找到 <relationships> 标签")
            return []

        content = match.group(1).strip()
        if not content:
            return []

        relationships = []
        for line_match in self.RELATIONSHIP_LINE_PATTERN.finditer(content):
            source = line_match.group(1).strip()
            target = line_match.group(2).strip()
            relation_type = line_match.group(3).strip().lower()

            if relation_type not in VALID_RELATION_TYPES:
                relation_type = "related"

            if source and target:
                relationships.append(
                    ExtractedRelationship(
                        source=source,
                        target=target,
                        relation_type=relation_type,
                    )
                )

        return relationships
