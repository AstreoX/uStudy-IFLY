"""Image Tools - AI 图表/图片生成工具"""

import base64
import logging
from typing import Any
from uuid import uuid4

import httpx

from chat.tools.base import ToolResult
from config import get_settings
from upload.storage import get_storage

logger = logging.getLogger(__name__)

# Gemini image generation model
_IMAGE_MODEL = "google/gemini-2.5-flash-image"
_IMAGE_TIMEOUT = 90  # seconds

# ============ Tool Definition ============

IMAGE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "generate_chart",
            "description": (
                "根据用户描述生成图表或图片。仅在用户明确要求绘制图表、生成图片时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "详细描述要生成的图表内容、样式、数据等",
                    },
                },
                "required": ["prompt"],
            },
        },
    },
]

IMAGE_TOOL_NAMES: set[str] = {t["function"]["name"] for t in IMAGE_TOOLS}


# ============ Executor ============

class ImageToolExecutor:
    """Executor for image generation tools"""

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        if tool_name != "generate_chart":
            return ToolResult(
                success=False,
                data=None,
                message=f"未知的工具: {tool_name}",
            )

        try:
            return await self._generate_chart(arguments)
        except Exception as e:
            logger.error(f"Image tool execution error: {e}", exc_info=True)
            return ToolResult(
                success=False,
                data=None,
                message=f"图表生成失败: {e!s}",
            )

    async def _generate_chart(self, args: dict[str, Any]) -> ToolResult:
        prompt = args.get("prompt", "")
        if not prompt:
            return ToolResult(
                success=False,
                data=None,
                message="请提供图表描述",
            )

        settings = get_settings()

        # Must use bridge for Google models (HK server cannot reach Google directly)
        if not settings.openrouter_bridge_url:
            return ToolResult(
                success=False,
                data=None,
                message="图片生成服务未配置（bridge URL 缺失）",
            )

        base_url = settings.openrouter_bridge_url.rstrip("/")
        api_key = settings.openrouter_api_key

        if not api_key:
            return ToolResult(
                success=False,
                data=None,
                message="图片生成服务未配置（API key 缺失）",
            )

        # Call OpenRouter with Gemini image generation model
        payload = {
            "model": _IMAGE_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": f"Please generate a chart/image as described: {prompt}",
                }
            ],
            "modalities": ["image", "text"],
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=_IMAGE_TIMEOUT) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        # Extract image from response
        choices = data.get("choices", [])
        if not choices:
            return ToolResult(
                success=False,
                data=None,
                message="图片生成失败：模型未返回结果",
            )

        message = choices[0].get("message", {})
        images = message.get("images", [])
        text_content = message.get("content", "")

        if not images:
            # Model returned text only, no image
            return ToolResult(
                success=False,
                data=None,
                message=f"模型未生成图片。模型回复: {text_content[:200]}",
            )

        # Decode and save the first image
        image_data_url = images[0]
        # Format: "data:image/png;base64,..." or raw base64
        if image_data_url.startswith("data:"):
            # Extract base64 portion after the comma
            _, b64_data = image_data_url.split(",", 1)
        else:
            b64_data = image_data_url

        image_bytes = base64.b64decode(b64_data)

        # Save to storage
        filename = f"{uuid4()}.png"
        storage = get_storage()
        image_path = await storage.save(image_bytes, filename, subdir="generated/charts")

        return ToolResult(
            success=True,
            data={
                "image_url": image_path,
                "description": text_content[:500] if text_content else "",
            },
            message="图表已生成",
        )
