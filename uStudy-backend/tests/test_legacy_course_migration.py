from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from uuid import UUID

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "migrate_legacy_user_courses.py"
)
SPEC = importlib.util.spec_from_file_location("legacy_course_migration", SCRIPT)
assert SPEC and SPEC.loader
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


def empty_records():
    return {name: [] for name in migration.TABLE_ORDER}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/uploads/notes/images/a.png", "notes/images/a.png"),
        ("uploads/images/space/doc/p.png", "images/space/doc/p.png"),
        ("/app/uploads/documents/course.pptx", "documents/course.pptx"),
        (
            "https://api.ustudy.cc/uploads/attachments/images/a.png",
            "attachments/images/a.png",
        ),
    ],
)
def test_candidate_upload_path_normalizes_allowed_paths(raw, expected):
    assert migration._candidate_upload_path(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "https://evil.example/uploads/a.png",
        "http://api.ustudy.cc/uploads/a.png",
        "/etc/passwd",
        "/uploads/../secret",
    ],
)
def test_candidate_upload_path_rejects_unsafe_paths(raw):
    with pytest.raises(RuntimeError):
        migration._candidate_upload_path(raw)


def test_embedded_upload_references_are_added_to_file_closure(monkeypatch):
    records = empty_records()
    records["messages"] = [
        {
            "id": "70000000-0000-0000-0000-000000000007",
            "content": "![chart](/uploads/artifacts/chart.png)",
            "tool_calls": [
                {
                    "result": {
                        "image": "https://api.ustudy.cc/uploads/artifacts/plot.webp"
                    }
                }
            ],
        }
    ]
    monkeypatch.setattr(migration, "EXPECTED_FILE_COUNT", 2)

    refs = migration.collect_file_references(records)

    assert set(refs) == {"artifacts/chart.png", "artifacts/plot.webp"}
    assert refs["artifacts/chart.png"]["kinds"] == ["embedded-reference"]


def test_file_magic_rejects_html_and_accepts_real_image_despite_bad_extension():
    jpeg = b"\xff\xd8\xff" + (b"x" * 20)
    assert migration.validate_file_magic("legacy.png", jpeg) == "image/jpeg"
    with pytest.raises(RuntimeError):
        migration.validate_file_magic("error.png", b"<html>not an image</html>")


def test_sanitize_value_maps_identity_paths_and_credentials():
    target = UUID("10000000-0000-0000-0000-000000000001")
    value = {
        "owner": str(migration.SOURCE_USER_ID),
        "image": "https://api.ustudy.cc/uploads/notes/a.png",
        "access_token": "must-not-survive",
        "nested": [{"api_key": "nope", "token_count": 17}],
    }

    sanitized = migration.sanitize_value(value, target)

    assert sanitized["owner"] == str(target)
    assert sanitized["image"] == "/uploads/notes/a.png"
    assert "access_token" not in sanitized
    assert "api_key" not in sanitized["nested"][0]
    assert sanitized["nested"][0]["token_count"] == 17


def test_transform_records_applies_course_and_private_content_rules():
    target = migration.EXAMPLE_USER_ID
    teacher = UUID("20000000-0000-0000-0000-000000000002")
    records = empty_records()
    records["spaces"] = [
        {
            "id": str(migration.NETWORK_SPACE_ID),
            "user_id": str(migration.SOURCE_USER_ID),
            "name": "计算机网络",
            "is_collaborative": True,
        }
    ]
    records["nodes"] = [
        {
            "id": "30000000-0000-0000-0000-000000000003",
            "space_id": str(migration.NETWORK_SPACE_ID),
            "label": "TCP",
            "mastery": 88,
        }
    ]
    records["edges"] = [
        {
            "id": "40000000-0000-0000-0000-000000000004",
            "space_id": str(migration.NETWORK_SPACE_ID),
            "type": "LEARNING_PATH",
            "user_id": str(migration.SOURCE_USER_ID),
        }
    ]
    records["notes"] = [
        {
            "id": "50000000-0000-0000-0000-000000000005",
            "space_id": str(migration.NETWORK_SPACE_ID),
            "creator_user_id": str(migration.SOURCE_USER_ID),
        }
    ]
    records["quizzes"] = [
        {
            "id": "60000000-0000-0000-0000-000000000006",
            "space_id": str(migration.NETWORK_SPACE_ID),
        }
    ]
    records["messages"] = [
        {
            "id": "70000000-0000-0000-0000-000000000007",
            "conversation_id": "80000000-0000-0000-0000-000000000008",
            "content": "kept",
            "llm_context": {"debug": "drop"},
        }
    ]

    transformed = migration.transform_records(
        records, target_user_id=target, teacher_id=teacher
    )

    assert transformed["spaces"][0]["user_id"] == str(teacher)
    assert transformed["nodes"][0]["mastery"] is None
    assert transformed["edges"][0]["user_id"] == str(target)
    assert transformed["notes"][0]["visibility"] == "private"
    assert transformed["notes"][0]["creator_user_id"] == str(target)
    assert transformed["quizzes"][0]["visibility"] == "private"
    assert transformed["quizzes"][0]["creator_user_id"] == str(target)
    assert transformed["messages"][0]["llm_context"] is None


def test_baseline_events_are_deterministic_and_scoped_to_example():
    records = empty_records()
    node_id = "30000000-0000-0000-0000-000000000003"
    mastery_id = "90000000-0000-0000-0000-000000000009"
    records["nodes"] = [
        {
            "id": node_id,
            "space_id": str(migration.OS_SPACE_ID),
            "label": "进程",
            "mastery": None,
        }
    ]
    records["node_user_mastery"] = [
        {
            "id": mastery_id,
            "node_id": node_id,
            "user_id": str(migration.EXAMPLE_USER_ID),
            "mastery": 72,
            "updated_at": "2026-05-01T12:00:00+00:00",
        }
    ]

    first = migration.baseline_mastery_events(records, migration.EXAMPLE_USER_ID)
    second = migration.baseline_mastery_events(records, migration.EXAMPLE_USER_ID)

    assert first == second
    assert first[0]["space_id"] == str(migration.OS_SPACE_ID)
    assert first[0]["user_id"] == str(migration.EXAMPLE_USER_ID)
    assert first[0]["created_at"] == "2026-05-01T12:00:00+00:00"
    assert first[0]["new_mastery"] == 72


def test_membership_ids_include_space_and_user():
    user = UUID("10000000-0000-0000-0000-000000000001")
    assert migration.membership_id(
        migration.NETWORK_SPACE_ID, user
    ) != migration.membership_id(migration.OS_SPACE_ID, user)
    assert migration.membership_id(
        migration.NETWORK_SPACE_ID, user
    ) == migration.membership_id(migration.NETWORK_SPACE_ID, user)


def test_stage_files_reuses_same_hash_and_rejects_different_content(tmp_path):
    bundle = tmp_path / "bundle"
    upload_root = tmp_path / "uploads"
    source = bundle / "files" / "notes" / "a.png"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"image")
    item = {
        "path": "notes/a.png",
        "bytes": 5,
        "sha256": hashlib.sha256(b"image").hexdigest(),
    }

    created, reused = migration.stage_files(bundle, {"files": [item]}, upload_root)
    assert len(created) == 1
    assert reused == []

    created, reused = migration.stage_files(bundle, {"files": [item]}, upload_root)
    assert created == []
    assert reused == ["notes/a.png"]

    (upload_root / "notes" / "a.png").write_bytes(b"other")
    with pytest.raises(RuntimeError):
        migration.stage_files(bundle, {"files": [item]}, upload_root)


def test_canonical_records_hash_is_order_stable():
    left = {"b": 2, "a": {"d": 4, "c": 3}}
    right = {"a": {"c": 3, "d": 4}, "b": 2}
    assert migration.sha256_bytes(
        migration.canonical_json(left).encode()
    ) == migration.sha256_bytes(migration.canonical_json(right).encode())
    assert json.loads(migration.canonical_json(left)) == right
