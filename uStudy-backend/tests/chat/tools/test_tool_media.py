"""Transient media must never leak into serialized tool results."""

import importlib.util
from pathlib import Path


def _load_base_module():
    path = Path(__file__).parents[3] / "chat" / "tools" / "base.py"
    spec = importlib.util.spec_from_file_location("tool_base_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_tool_result_serialization_excludes_all_transient_media():
    module = _load_base_module()
    media = module.ToolMedia(
        base64_data="c2VjcmV0LWJ5dGVz",
        mime_type="image/webp",
        label="PDF physical page 1-4",
        physical_page_start=1,
        physical_page_end=4,
    )
    result = module.ToolResult(
        success=True,
        data={"assets": [{"physical_page_start": 1}]},
        message="loaded",
        image_base64="legacy-secret",
        media=[media],
    )

    assert result.to_dict() == {
        "success": True,
        "data": {"assets": [{"physical_page_start": 1}]},
        "message": "loaded",
    }
    assert "c2VjcmV0" not in str(result.to_dict())
    assert "legacy-secret" not in str(result.to_dict())


def test_consumed_tool_media_is_replaced_after_one_model_turn():
    module = _load_base_module()
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": module.TRANSIENT_TOOL_MEDIA_PROMPT},
                {"type": "text", "text": "PDF physical pages 1-4"},
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/webp;base64,c2VjcmV0"},
                },
            ],
        },
        {"role": "user", "content": "ordinary message"},
    ]

    module.strip_consumed_tool_media(messages)

    assert isinstance(messages[0]["content"], str)
    assert "PDF physical pages 1-4" in messages[0]["content"]
    assert "base64" not in messages[0]["content"]
    assert messages[1]["content"] == "ordinary message"


def test_media_budget_trims_asset_metadata_before_citations_are_registered():
    module = _load_base_module()

    def result_for(start: int):
        media = [
            module.ToolMedia(
                base64_data="YQ==",
                mime_type="image/webp",
                label=f"page {page}",
                physical_page_start=page,
                physical_page_end=page,
            )
            for page in range(start, start + 4)
        ]
        return module.ToolResult(
            success=True,
            data={
                "assets": [
                    {"physical_page_start": item.physical_page_start} for item in media
                ]
            },
            message="loaded",
            media=media,
        )

    first = result_for(1)
    second = result_for(5)
    used_count, used_bytes = module.apply_tool_media_budget(
        first, max_images=4, max_bytes=100
    )
    assert used_count == 4
    assert used_bytes > 0
    second_count, _ = module.apply_tool_media_budget(
        second, max_images=0, max_bytes=100 - used_bytes
    )

    assert second_count == 0
    assert second.media == []
    assert second.data["assets"] == []
    assert len(second.data["omitted_assets"]) == 4
    assert second.data["media_omitted_count"] == 4


def test_duplicate_legacy_image_is_not_double_counted_when_media_is_omitted():
    module = _load_base_module()
    media = module.ToolMedia(
        base64_data="YQ==",
        mime_type="image/png",
        label="page 1",
        physical_page_start=1,
        physical_page_end=1,
    )
    result = module.ToolResult(
        success=True,
        data={"page_number": 1},
        message="loaded",
        image_base64="YQ==",
        media=[media],
    )

    delivered, _ = module.apply_tool_media_budget(result, max_images=0, max_bytes=0)

    assert delivered == 0
    assert result.media == []
    assert result.image_base64 is None
    assert result.data["media_omitted_count"] == 1
    assert module.page_assets_for_citation(result.data) == []


def test_page_citation_fallback_only_applies_to_delivered_legacy_single_page():
    module = _load_base_module()

    assert module.page_assets_for_citation({"assets": []}) == []
    assert (
        module.page_assets_for_citation({"page_number": 7, "media_omitted_count": 1})
        == []
    )
    assert module.page_assets_for_citation({"page_number": 7}) == [
        {"physical_page_start": 7, "physical_page_end": 7}
    ]
