"""Image tool schema and description guardrail tests."""

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path


def _load_image_tools():
    """Load image_tools directly without importing the heavy chat.tools package."""
    patched_module_names = [
        "chat",
        "chat.tools",
        "chat.tools.base",
        "config",
        "upload",
        "upload.storage",
    ]
    original_modules = {
        name: sys.modules.get(name)
        for name in patched_module_names
    }

    @dataclass
    class _ToolResult:
        success: bool
        data: object
        message: str
        image_base64: str | None = None

    sys.modules.setdefault("chat", types.ModuleType("chat"))
    tools_pkg = sys.modules.setdefault("chat.tools", types.ModuleType("chat.tools"))
    tools_pkg.__path__ = []  # type: ignore[attr-defined]

    base_mod = types.ModuleType("chat.tools.base")
    base_mod.ToolResult = _ToolResult  # type: ignore[attr-defined]
    sys.modules["chat.tools.base"] = base_mod

    config_mod = types.ModuleType("config")
    config_mod.get_settings = lambda: object()  # type: ignore[attr-defined]
    sys.modules["config"] = config_mod

    storage_mod = types.ModuleType("upload.storage")
    storage_mod.get_storage = lambda: object()  # type: ignore[attr-defined]
    sys.modules.setdefault("upload", types.ModuleType("upload"))
    sys.modules["upload.storage"] = storage_mod

    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "chat" / "tools" / "image_tools.py"
    )
    spec = importlib.util.spec_from_file_location("chat.tools.image_tools", module_path)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    finally:
        for name, original_module in original_modules.items():
            if original_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original_module
    return mod


_image_tools = _load_image_tools()
IMAGE_TOOLS = _image_tools.IMAGE_TOOLS
IMAGE_TOOL_NAMES = _image_tools.IMAGE_TOOL_NAMES
ImageToolExecutor = _image_tools.ImageToolExecutor


def test_only_generate_image_is_registered():
    assert IMAGE_TOOL_NAMES == {"generate_image"}
    assert [tool["function"]["name"] for tool in IMAGE_TOOLS] == ["generate_image"]


def test_generate_image_requires_description():
    tool = IMAGE_TOOLS[0]

    assert tool["function"]["parameters"]["required"] == ["description"]
    assert "description" in tool["function"]["parameters"]["properties"]
    assert "prompt" not in tool["function"]["parameters"]["properties"]
    assert "必须传入 description" in tool["function"]["description"]


def test_extract_description_does_not_accept_legacy_prompt():
    assert ImageToolExecutor._extract_description({"prompt": "old field"}) == ""
    assert ImageToolExecutor._extract_description({"description": " new image "}) == "new image"


def test_build_image_request_text_preserves_structured_context():
    text = ImageToolExecutor._build_image_request_text(
        {
            "title": "根系吸收机制图",
            "image_type": "diagram",
            "style": "论文机制图，白底，矢量风格",
        },
        "展示根系吸收微纳米塑料的路径，并标注关键箭头。",
    )

    assert "图片需求：展示根系吸收微纳米塑料的路径" in text
    assert "标题：根系吸收机制图" in text
    assert "图片类型：diagram" in text
    assert "视觉风格：论文机制图" in text
    assert "不要替换成无关主题" in text


def test_normalize_openai_images_endpoint_accepts_root_or_v1_base_url():
    assert (
        ImageToolExecutor._normalize_openai_images_endpoint("https://openapi.center")
        == "https://openapi.center/v1/images/generations"
    )
    assert (
        ImageToolExecutor._normalize_openai_images_endpoint("https://openapi.center/v1")
        == "https://openapi.center/v1/images/generations"
    )
    assert (
        ImageToolExecutor._normalize_openai_images_endpoint(
            "https://openapi.center/v1/images/generations"
        )
        == "https://openapi.center/v1/images/generations"
    )


def test_normalize_openai_images_endpoint_can_switch_to_edits():
    assert (
        ImageToolExecutor._normalize_openai_images_endpoint(
            "https://openapi.center",
            "edits",
        )
        == "https://openapi.center/v1/images/edits"
    )
    assert (
        ImageToolExecutor._normalize_openai_images_endpoint(
            "https://openapi.center/v1/images/generations",
            "edits",
        )
        == "https://openapi.center/v1/images/edits"
    )


def test_extract_openai_image_response_reads_b64_json():
    b64_data, revised_prompt, error_message = (
        ImageToolExecutor._extract_openai_image_response(
            {
                "data": [
                    {
                        "b64_json": "abc123",
                        "revised_prompt": "polished prompt",
                    }
                ]
            }
        )
    )

    assert b64_data == "abc123"
    assert revised_prompt == "polished prompt"
    assert error_message == ""


def test_reference_image_filename_uses_content_type_extension():
    assert ImageToolExecutor._reference_image_filename(1, "image/jpeg") == "reference-1.jpg"
    assert ImageToolExecutor._reference_image_filename(2, "image/webp") == "reference-2.webp"
    assert ImageToolExecutor._reference_image_filename(3, None) == "reference-3.png"
