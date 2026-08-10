"""Base data structures for the crawler module."""

from dataclasses import dataclass, field


@dataclass
class ContentResult:
    """Unified content extraction result."""

    content: str  # Extracted markdown/text
    title: str
    url: str
    content_type: str  # "webpage" | "video_transcript"
    extraction_method: str  # "trafilatura" | "crawl4ai" | "jina" | "regex"
    metadata: dict = field(default_factory=dict)
