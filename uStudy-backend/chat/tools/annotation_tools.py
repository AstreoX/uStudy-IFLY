"""Annotation Tools - Rectangle overlay with text comments for dual-panel sync"""

from chat.tools.base import ToolResult


ANNOTATION_TOOLS = [{
    "type": "function",
    "function": {
        "name": "annotate_panel",
        "description": "在左面板截图上画方框并标注批注。使用百分比坐标定位。",
        "parameters": {
            "type": "object",
            "properties": {
                "annotations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "number", "description": "方框左上角 x 百分比 (0-100)"},
                            "y": {"type": "number", "description": "方框左上角 y 百分比 (0-100)"},
                            "w": {"type": "number", "description": "方框宽度百分比"},
                            "h": {"type": "number", "description": "方框高度百分比"},
                            "comment": {"type": "string", "description": "批注文字"},
                            "color": {"type": "string", "description": "方框颜色, 默认 #FF6B6B"}
                        },
                        "required": ["x", "y", "w", "h", "comment"]
                    }
                }
            },
            "required": ["annotations"]
        }
    }
}]

ANNOTATION_TOOL_NAMES = {"annotate_panel"}


class AnnotationToolExecutor:
    """Pass-through executor: validates and returns annotation data for frontend rendering."""

    async def execute(self, tool_name: str, arguments: dict) -> ToolResult:
        annotations = arguments.get("annotations", [])
        return ToolResult(
            success=True,
            data={"annotations": annotations, "count": len(annotations)},
            message=f"已标注 {len(annotations)} 处",
        )
