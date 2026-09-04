"""Image Tools - AI 图片生成工具"""

import base64
import logging
import time
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from chat.tools.base import ToolResult
from config import get_settings
from upload.storage import get_storage

try:
    from usage.observability import record_ai_request_log
except Exception:
    async def record_ai_request_log(**_: Any) -> None:
        return None

logger = logging.getLogger(__name__)

# ============ Tool Definition ============

GENERATE_IMAGE_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "generate_image",
        "description": (
            "根据用户需求生成图片、配图、机制图、流程图、示意图、信息图或数据图。"
            "仅在用户明确要求画图、生成图片/配图/机制图/图表时使用。"
            "必须传入 description，完整保留用户想画的主体、关键元素、文字标签、布局关系、"
            "风格、颜色、比例、数据或学术约束；不要只传标题或泛泛描述。"
            "生成的图片会自动保存为笔记。请提供简短标题(title)，"
            "并根据对话上下文判断最相关的知识节点名称(node_label)传入。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": (
                        "详细图片生成描述。必须包含用户原始需求中的核心内容、对象、关系、布局、"
                        "文字标注、风格、颜色、尺寸比例、数据点或参考图使用方式。"
                    ),
                },
                "title": {
                    "type": "string",
                    "description": "图片的简短标题，用于保存笔记，如'人体肌肉解剖图'、'光合作用流程图'",
                },
                "image_type": {
                    "type": "string",
                    "enum": [
                        "diagram",
                        "illustration",
                        "infographic",
                        "chart",
                        "concept_art",
                        "other",
                    ],
                    "description": "图片类型。机制图/流程图/结构图选 diagram，数据图选 chart。",
                },
                "style": {
                    "type": "string",
                    "description": "视觉风格要求，如'论文机制图，白底，矢量风格，清晰标签'。可选。",
                },
                "node_label": {
                    "type": "string",
                    "description": (
                        "将图片挂载到的知识节点名称。请根据当前对话主题和空间知识图谱，"
                        "选择最相关的节点名称。不传或传 'FREE' 表示不挂载到任何节点。"
                    ),
                },
            },
            "required": ["description"],
        },
    },
}

IMAGE_TOOLS: list[dict[str, Any]] = [
    GENERATE_IMAGE_TOOL,
]

IMAGE_TOOL_NAMES: set[str] = {t["function"]["name"] for t in IMAGE_TOOLS}


# ============ Executor ============


class ImageToolExecutor:
    """Executor for image generation tools"""

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        reference_image_urls: list[str] | None = None,
    ) -> ToolResult:
        if tool_name not in IMAGE_TOOL_NAMES:
            return ToolResult(
                success=False,
                data=None,
                message=f"未知的工具: {tool_name}",
            )

        try:
            return await self._generate_image(arguments, reference_image_urls)
        except Exception as e:
            logger.error(f"Image tool execution error: {e}", exc_info=True)
            return ToolResult(
                success=False,
                data=None,
                message=f"图片生成失败: {e!s}",
            )

    @staticmethod
    def _extract_description(args: dict[str, Any]) -> str:
        """Extract the required image description."""
        return (args.get("description") or "").strip()

    @staticmethod
    def _build_image_request_text(args: dict[str, Any], description: str) -> str:
        """Build a richer prompt for the image model from structured tool args."""
        parts = [f"图片需求：{description}"]
        title = (args.get("title") or "").strip()
        image_type = (args.get("image_type") or "").strip()
        style = (args.get("style") or "").strip()
        if title:
            parts.append(f"标题：{title}")
        if image_type:
            parts.append(f"图片类型：{image_type}")
        if style:
            parts.append(f"视觉风格：{style}")
        parts.append(
            "请严格围绕上述需求生成图片，保留关键文字标签、主体关系和用户指定的布局/数据；"
            "不要替换成无关主题。"
        )
        return "\n".join(parts)

    @staticmethod
    def _normalize_openai_images_endpoint(
        base_url: str,
        operation: str = "generations",
    ) -> str:
        """Build the image generation endpoint from a root or /v1 base URL."""
        clean_url = (base_url or "").rstrip("/")
        if not clean_url:
            return ""

        operation = operation.strip("/")
        parsed = urlparse(clean_url)
        path = parsed.path.rstrip("/").lower()
        if path.endswith("/images/generations") or path.endswith("/images/edits"):
            images_base_url = clean_url.rsplit("/", 1)[0]
            return f"{images_base_url}/{operation}"
        if path.endswith(f"/images/{operation}"):
            return clean_url
        if path.endswith("/v1") or path.endswith("/api/v1"):
            return f"{clean_url}/images/{operation}"
        return f"{clean_url}/v1/images/{operation}"

    @staticmethod
    def _strip_data_url(image_data: str) -> str:
        if image_data.startswith("data:"):
            _, b64_data = image_data.split(",", 1)
            return b64_data
        return image_data

    @staticmethod
    def _extract_openai_image_response(data: dict[str, Any]) -> tuple[str, str, str]:
        """Return (b64_data, revised_prompt, error_message) from Images API response."""
        images = data.get("data") or []
        if not images:
            return "", "", "图片生成失败：模型未返回图片数据"

        first_image = images[0] or {}
        revised_prompt = (first_image.get("revised_prompt") or "").strip()
        b64_data = (first_image.get("b64_json") or "").strip()
        if b64_data:
            return b64_data, revised_prompt, ""

        image_url = (first_image.get("url") or "").strip()
        if image_url:
            return image_url, revised_prompt, ""

        return "", revised_prompt, "图片生成失败：无法解析图片数据"

    async def _generate_image(
        self,
        args: dict[str, Any],
        reference_image_urls: list[str] | None = None,
    ) -> ToolResult:
        description = self._extract_description(args)
        if not description:
            return ToolResult(
                success=False,
                data=None,
                message="图片生成失败：缺少 description。请用 description 详细说明要生成的图片内容、关键元素、布局、风格和文字标注。",
            )
        prompt = self._build_image_request_text(args, description)

        settings = get_settings()
        return await self._generate_openai_image(
            prompt, settings, reference_image_urls
        )

    @staticmethod
    def _reference_image_filename(index: int, content_type: str | None) -> str:
        extension_by_type = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }
        extension = extension_by_type.get((content_type or "").split(";")[0], "png")
        return f"reference-{index}.{extension}"

    async def _download_reference_images(
        self,
        client: httpx.AsyncClient,
        reference_image_urls: list[str],
    ) -> list[tuple[str, tuple[str, bytes, str]]]:
        files: list[tuple[str, tuple[str, bytes, str]]] = []
        for index, image_url in enumerate(reference_image_urls[:4], start=1):
            response = await client.get(image_url)
            response.raise_for_status()
            content_type = response.headers.get("content-type") or "image/png"
            filename = self._reference_image_filename(index, content_type)
            files.append(("image[]", (filename, response.content, content_type)))
        return files

    async def _generate_openai_image(
        self,
        prompt: str,
        settings: Any,
        reference_image_urls: list[str] | None = None,
    ) -> ToolResult:
        base_url = (
            getattr(settings, "image_generation_base_url", "")
            or "https://api.openai.com"
        )
        reference_image_urls = [url for url in (reference_image_urls or []) if url]
        operation = "edits" if reference_image_urls else "generations"
        endpoint_url = self._normalize_openai_images_endpoint(base_url, operation)
        api_key = (
            getattr(settings, "image_generation_api_key", "")
            or getattr(settings, "openai_api_key", "")
        )

        if not endpoint_url:
            return ToolResult(
                success=False,
                data=None,
                message="图片生成服务未配置（base URL 缺失）",
            )
        if not api_key:
            return ToolResult(
                success=False,
                data=None,
                message="图片生成服务未配置（API key 缺失）",
            )

        payload: dict[str, Any] = {
            "model": settings.image_generation_model,
            "prompt": prompt,
        }
        size = (getattr(settings, "image_generation_size", "") or "").strip()
        quality = (getattr(settings, "image_generation_quality", "") or "").strip()
        output_format = (
            getattr(settings, "image_generation_output_format", "") or ""
        ).strip()
        if size:
            payload["size"] = size
        if quality:
            payload["quality"] = quality
        if output_format:
            payload["output_format"] = output_format

        headers = {
            "Authorization": f"Bearer {api_key}",
        }

        t_start = time.monotonic()
        response_status: int | None = None
        try:
            async with httpx.AsyncClient(
                timeout=settings.image_generation_timeout_seconds
            ) as client:
                if reference_image_urls:
                    files = await self._download_reference_images(
                        client, reference_image_urls
                    )
                    response = await client.post(
                        endpoint_url,
                        data=payload,
                        files=files,
                        headers=headers,
                    )
                else:
                    response = await client.post(
                        endpoint_url,
                        json=payload,
                        headers={
                            **headers,
                            "Content-Type": "application/json",
                        },
                    )
                response_status = response.status_code
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            await record_ai_request_log(
                model=settings.image_generation_model,
                base_url=endpoint_url,
                request_kind="image_generation",
                source_module="chat",
                source_operation="image_generation",
                status="failure",
                latency_ms=int((time.monotonic() - t_start) * 1000),
                error=e,
                http_status_code=response_status,
                message_count=1,
                context_chars=len(prompt),
            )
            raise

        image_data, revised_prompt, error_message = (
            self._extract_openai_image_response(data)
        )
        if error_message:
            await record_ai_request_log(
                model=settings.image_generation_model,
                base_url=endpoint_url,
                request_kind="image_generation",
                source_module="chat",
                source_operation="image_generation",
                status="failure",
                latency_ms=int((time.monotonic() - t_start) * 1000),
                usage=data.get("usage"),
                http_status_code=response_status,
                error=Exception(error_message),
                message_count=1,
                context_chars=len(prompt),
            )
            return ToolResult(
                success=False,
                data=None,
                message=error_message,
            )

        if image_data.startswith("http://") or image_data.startswith("https://"):
            try:
                async with httpx.AsyncClient(
                    timeout=settings.image_generation_timeout_seconds
                ) as client:
                    image_response = await client.get(image_data)
                    image_response.raise_for_status()
                    image_bytes = image_response.content
                b64_data = base64.b64encode(image_bytes).decode("ascii")
            except Exception as e:
                await record_ai_request_log(
                    model=settings.image_generation_model,
                    base_url=endpoint_url,
                    request_kind="image_generation",
                    source_module="chat",
                    source_operation="image_generation",
                    status="failure",
                    latency_ms=int((time.monotonic() - t_start) * 1000),
                    usage=data.get("usage"),
                    http_status_code=response_status,
                    error=e,
                    message_count=1,
                    context_chars=len(prompt),
                )
                raise
        else:
            b64_data = self._strip_data_url(image_data)
            image_bytes = base64.b64decode(b64_data)

        filename = f"{uuid4()}.png"
        storage = get_storage()
        image_path = await storage.save(
            image_bytes, filename, subdir="generated/images"
        )

        await record_ai_request_log(
            model=settings.image_generation_model,
            base_url=endpoint_url,
            request_kind="image_generation",
            source_module="chat",
            source_operation="image_generation",
            status="success",
            latency_ms=int((time.monotonic() - t_start) * 1000),
            usage=data.get("usage"),
            http_status_code=response_status,
            message_count=1,
            context_chars=len(prompt),
        )

        return ToolResult(
            success=True,
            data={
                "image_url": image_path,
                "description": revised_prompt[:500] if revised_prompt else "",
            },
            message="图片已生成",
            image_base64=b64_data,
        )
