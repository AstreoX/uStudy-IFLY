"""Base classes for chat tools"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolResult:
    """Result of a tool execution"""

    success: bool
    data: Any
    message: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message,
        }
