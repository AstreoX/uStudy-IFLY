"""Memory system schemas"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from db.models import MemoryType


@dataclass
class MemorySearchResult:
    """记忆搜索结果"""

    id: UUID
    content: str
    score: float
    memory_type: MemoryType
    created_at: datetime
    space_id: UUID | None = None
    extra_data: dict | None = None


@dataclass
class ExtractionResult:
    """记忆提取结果"""

    long_term_count: int
    space_count: int
    long_term_contents: list[str]
    space_contents: list[str]
