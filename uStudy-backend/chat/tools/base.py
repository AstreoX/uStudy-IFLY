"""Base classes for chat tools"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """Result of a tool execution"""

    success: bool
    data: Any
    message: str
    image_base64: str | None = None  # Transient: for injecting visual context, not serialized

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message,
        }
