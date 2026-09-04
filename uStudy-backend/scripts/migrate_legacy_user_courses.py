"""Migrate two allow-listed legacy courses into the experiment deployment.

This utility intentionally does not use ORM models from the legacy database.  A
PostgreSQL 17 custom dump is first restored into an isolated database, then this
script exports only the selected course/user closure into a checksummed bundle.
The import side runs against the current application database and applies the
documented identity, visibility, and ownership transforms transactionally.

The bundle contains private user content.  Keep it outside the repository and
delete it after the migration has been verified.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
import re
import shutil
import ssl
import sys
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID, uuid4, uuid5

import asyncpg

SOURCE_USER_ID = UUID("154c691b-52c2-45fe-9c0b-75ade6f1ae8f")
EXAMPLE_USER_ID = UUID("a3fc453d-1188-4fb0-bbc3-3a523cf1023a")
SYSTEM_USER_ID = UUID("a0c4ccd2-328d-50c2-a23d-249911c274ee")
DEFAULT_SPACE_ID = UUID("fb40acea-11d5-572f-b987-e08cf9e152b5")
NETWORK_SPACE_ID = UUID("d0fcc14b-56a5-4fa9-9f30-07cb712d8e5d")
OS_SPACE_ID = UUID("f69c53cf-e561-4e12-884c-88e3a35659dc")
SOURCE_SPACE_IDS = (NETWORK_SPACE_ID, OS_SPACE_ID)
EXPECTED_SPACE_NAMES = {
    str(NETWORK_SPACE_ID): "计算机网络",
    str(OS_SPACE_ID): "计算机操作系统",
}
EXPECTED_SOURCE_DUMP_SHA256 = (
    "6304d3c08690a5f073ff1c4926a0864832f3a6e91906e440f0621e49cb43751e"
)
EXPECTED_CURRENT_STUDENTS = 103
EXPECTED_STUDENT_ROSTER_SHA256 = (
    "73b561a3cdc059acf4b5cf82343a85d27e00377c154b69f981a5c6effd4c6ea0"
)
EXPECTED_FILE_COUNT = 61
EXPECTED_TABLE_COUNTS = {
    "spaces": 2,
    "nodes": 180,
    "edges": 223,
    "folders": 2,
    "notes": 42,
    "note_attachments": 7,
    "conversations": 125,
    "messages": 663,
    "conversation_agent_todos": 26,
    "message_attachments": 16,
    "agent_tasks": 33,
    "quizzes": 7,
    "questions": 51,
    "quiz_attempts": 3,
    "node_user_mastery": 49,
    "learning_path_events": 5,
    "study_activity_logs": 42,
    "review_schedules": 215,
    "vector_memories": 4,
    "space_memories": 0,
    "calendar_events": 0,
    "space_documents": 1,
    "document_processing_tasks": 1,
    "document_chunks": 0,
    "document_texts": 1,
    "document_images": 14,
}
MIGRATION_NAMESPACE = UUID("3937fa41-cf47-5ac4-ac67-dba3059706a5")
ADVISORY_LOCK_KEY = 0x5553545544594D47
BUNDLE_VERSION = 1
ALLOWED_SOURCE_HOST = "api.ustudy.cc"
SENSITIVE_JSON_KEYS = {
    "password",
    "password_hash",
    "secret",
    "secret_key",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "api_key_encrypted",
    "capability",
    "capability_token",
    "capability_token_hash",
}
EMBEDDED_UPLOAD_RE = re.compile(
    r"(?:https://api\.ustudy\.cc)?(?:/app)?/?uploads/[A-Za-z0-9._~%/+-]+",
    re.IGNORECASE,
)

TABLE_ORDER = (
    "spaces",
    "nodes",
    "edges",
    "folders",
    "space_documents",
    "document_texts",
    "document_images",
    "document_chunks",
    "document_processing_tasks",
    "notes",
    "note_attachments",
    "conversations",
    "messages",
    "conversation_agent_todos",
    "message_attachments",
    "agent_tasks",
    "quizzes",
    "questions",
    "quiz_attempts",
    "node_user_mastery",
    "learning_path_events",
    "study_activity_logs",
    "review_schedules",
    "vector_memories",
    "space_memories",
    "calendar_events",
)


def _json_default(value: Any) -> Any:
    if isinstance(value, (UUID, datetime, date)):
        return value.isoformat() if hasattr(value, "isoformat") else str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, memoryview):
        return value.tobytes().hex()
    raise TypeError(f"cannot JSON encode {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


ISO_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$"
)


def normalize_for_compare(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: normalize_for_compare(child) for key, child in value.items()}
    if isinstance(value, list):
        return [normalize_for_compare(child) for child in value]
    if isinstance(value, str) and ISO_DATETIME_RE.match(value):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
        return parsed.isoformat(timespec="microseconds")
    return value


def comparable_json(value: Any) -> str:
    return canonical_json(normalize_for_compare(value))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_dsn(dsn: str) -> str:
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


async def connect(dsn: str) -> asyncpg.Connection:
    conn = await asyncpg.connect(normalize_dsn(dsn))
    await conn.set_type_codec(
        "json", schema="pg_catalog", encoder=json.dumps, decoder=json.loads
    )
    await conn.set_type_codec(
        "jsonb", schema="pg_catalog", encoder=json.dumps, decoder=json.loads
    )
    return conn


def rows_to_json(rows: Iterable[asyncpg.Record]) -> list[dict[str, Any]]:
    return [json.loads(canonical_json(dict(row))) for row in rows]


async def fetch_json(
    conn: asyncpg.Connection, sql: str, *args: Any
) -> list[dict[str, Any]]:
    return rows_to_json(await conn.fetch(sql, *args))


async def export_records(conn: asyncpg.Connection) -> dict[str, list[dict[str, Any]]]:
    spaces = list(SOURCE_SPACE_IDS)
    records: dict[str, list[dict[str, Any]]] = {}
    records["spaces"] = await fetch_json(
        conn,
        "SELECT * FROM spaces WHERE id = ANY($1::uuid[]) ORDER BY id",
        spaces,
    )
    records["nodes"] = await fetch_json(
        conn, "SELECT * FROM nodes WHERE space_id = ANY($1::uuid[]) ORDER BY id", spaces
    )
    node_ids = [UUID(row["id"]) for row in records["nodes"]]
    records["edges"] = await fetch_json(
        conn, "SELECT * FROM edges WHERE space_id = ANY($1::uuid[]) ORDER BY id", spaces
    )
    records["folders"] = await fetch_json(
        conn,
        "SELECT * FROM folders WHERE space_id = ANY($1::uuid[]) ORDER BY id",
        spaces,
    )
    records["space_documents"] = await fetch_json(
        conn,
        "SELECT * FROM space_documents WHERE space_id = ANY($1::uuid[]) ORDER BY id",
        spaces,
    )
    document_ids = [UUID(row["id"]) for row in records["space_documents"]]
    for table in (
        "document_processing_tasks",
        "document_chunks",
        "document_texts",
        "document_images",
    ):
        records[table] = await fetch_json(
            conn,
            f"SELECT * FROM {table} WHERE document_id = ANY($1::uuid[]) ORDER BY id",
            document_ids,
        )

    records["notes"] = await fetch_json(
        conn,
        """
        SELECT * FROM notes
        WHERE space_id = ANY($1::uuid[]) AND creator_user_id = $2
        ORDER BY id
        """,
        spaces,
        SOURCE_USER_ID,
    )
    note_ids = [UUID(row["id"]) for row in records["notes"]]
    records["note_attachments"] = await fetch_json(
        conn,
        "SELECT * FROM note_attachments WHERE note_id = ANY($1::uuid[]) ORDER BY id",
        note_ids,
    )
    records["conversations"] = await fetch_json(
        conn,
        """
        SELECT * FROM conversations
        WHERE space_id = ANY($1::uuid[]) AND user_id = $2
        ORDER BY id
        """,
        spaces,
        SOURCE_USER_ID,
    )
    conversation_ids = [UUID(row["id"]) for row in records["conversations"]]
    records["messages"] = await fetch_json(
        conn,
        "SELECT * FROM messages WHERE conversation_id = ANY($1::uuid[]) ORDER BY id",
        conversation_ids,
    )
    message_ids = [UUID(row["id"]) for row in records["messages"]]
    records["conversation_agent_todos"] = await fetch_json(
        conn,
        """
        SELECT * FROM conversation_agent_todos
        WHERE conversation_id = ANY($1::uuid[]) ORDER BY id
        """,
        conversation_ids,
    )
    records["message_attachments"] = await fetch_json(
        conn,
        """
        SELECT * FROM message_attachments
        WHERE message_id = ANY($1::uuid[]) AND user_id = $2
        ORDER BY id
        """,
        message_ids,
        SOURCE_USER_ID,
    )
    records["agent_tasks"] = await fetch_json(
        conn,
        """
        SELECT * FROM agent_tasks
        WHERE space_id = ANY($1::uuid[]) AND user_id = $2
          AND status::text IN ('DONE', 'FAILED')
        ORDER BY id
        """,
        spaces,
        SOURCE_USER_ID,
    )
    records["quizzes"] = await fetch_json(
        conn,
        "SELECT * FROM quizzes WHERE space_id = ANY($1::uuid[]) ORDER BY id",
        spaces,
    )
    quiz_ids = [UUID(row["id"]) for row in records["quizzes"]]
    records["questions"] = await fetch_json(
        conn,
        "SELECT * FROM questions WHERE quiz_id = ANY($1::uuid[]) ORDER BY id",
        quiz_ids,
    )
    records["quiz_attempts"] = await fetch_json(
        conn,
        """
        SELECT * FROM quiz_attempts
        WHERE quiz_id = ANY($1::uuid[]) AND user_id = $2
        ORDER BY id
        """,
        quiz_ids,
        SOURCE_USER_ID,
    )
    records["node_user_mastery"] = await fetch_json(
        conn,
        """
        SELECT * FROM node_user_mastery
        WHERE node_id = ANY($1::uuid[]) AND user_id = $2
        ORDER BY id
        """,
        node_ids,
        SOURCE_USER_ID,
    )
    records["learning_path_events"] = await fetch_json(
        conn,
        """
        SELECT * FROM learning_path_events
        WHERE space_id = ANY($1::uuid[]) AND user_id = $2
        ORDER BY id
        """,
        spaces,
        SOURCE_USER_ID,
    )
    records["study_activity_logs"] = await fetch_json(
        conn,
        """
        SELECT * FROM study_activity_logs
        WHERE space_id = ANY($1::uuid[]) AND user_id = $2
        ORDER BY id
        """,
        spaces,
        SOURCE_USER_ID,
    )
    activity_ids = [UUID(row["id"]) for row in records["study_activity_logs"]]
    records["review_schedules"] = await fetch_json(
        conn,
        """
        SELECT * FROM review_schedules
        WHERE user_id = $3
          AND (activity_id = ANY($1::uuid[]) OR review_quiz_id = ANY($2::uuid[]))
        ORDER BY id
        """,
        activity_ids,
        quiz_ids,
        SOURCE_USER_ID,
    )
    records["vector_memories"] = await fetch_json(
        conn,
        """
        SELECT * FROM vector_memories
        WHERE space_id = ANY($1::uuid[]) AND user_id = $2
        ORDER BY id
        """,
        spaces,
        SOURCE_USER_ID,
    )
    records["space_memories"] = await fetch_json(
        conn,
        "SELECT * FROM space_memories WHERE space_id = ANY($1::uuid[]) ORDER BY id",
        spaces,
    )
    records["calendar_events"] = await fetch_json(
        conn,
        """
        SELECT * FROM calendar_events
        WHERE user_id = $2 AND source_conversation_id = ANY($1::uuid[])
        ORDER BY id
        """,
        conversation_ids,
        SOURCE_USER_ID,
    )
    return {name: records.get(name, []) for name in TABLE_ORDER}


def validate_export(records: Mapping[str, list[dict[str, Any]]]) -> None:
    actual = {name: len(records.get(name, [])) for name in EXPECTED_TABLE_COUNTS}
    if actual != EXPECTED_TABLE_COUNTS:
        raise RuntimeError(
            "source selection count mismatch: "
            + canonical_json({"expected": EXPECTED_TABLE_COUNTS, "actual": actual})
        )
    names = {row["id"]: row["name"] for row in records["spaces"]}
    if names != EXPECTED_SPACE_NAMES:
        raise RuntimeError(f"source course identity mismatch: {canonical_json(names)}")
    for edge in records["edges"]:
        edge_type = edge.get("type")
        user_id = edge.get("user_id")
        if edge_type == "LEARNING_PATH" and user_id != str(SOURCE_USER_ID):
            raise RuntimeError(
                "learning-path edge is not owned by the selected source user"
            )
        if edge_type != "LEARNING_PATH" and user_id is not None:
            raise RuntimeError("shared graph edge unexpectedly has a user owner")
    bad_tasks = [
        row["id"]
        for row in records["agent_tasks"]
        if row["status"] not in {"DONE", "FAILED"}
    ]
    if bad_tasks:
        raise RuntimeError(f"non-terminal agent tasks selected: {len(bad_tasks)}")


def _candidate_upload_path(raw: str) -> str:
    value = urllib.parse.unquote(raw.strip()).replace("\\", "/")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme:
        if parsed.scheme != "https" or parsed.hostname != ALLOWED_SOURCE_HOST:
            raise RuntimeError("file URL uses a non-allow-listed origin")
        value = parsed.path
    if value.startswith("/app/uploads/"):
        value = value[len("/app") :]
    elif value.startswith("uploads/"):
        value = "/" + value
    marker = value.find("/uploads/")
    if marker > 0:
        value = value[marker:]
    if not value.startswith("/uploads/"):
        raise RuntimeError("file path is outside /uploads")
    relative = PurePosixPath(value[len("/uploads/") :])
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise RuntimeError("unsafe upload path")
    return relative.as_posix()


def collect_file_references(
    records: Mapping[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}

    def add(raw: str | None, expected_size: int | None, kind: str) -> None:
        if not raw:
            return
        relative = _candidate_upload_path(raw)
        current = refs.setdefault(
            relative, {"expected_size": expected_size, "kinds": []}
        )
        if current["expected_size"] is None and expected_size is not None:
            current["expected_size"] = expected_size
        if expected_size is not None and current["expected_size"] != expected_size:
            raise RuntimeError("conflicting expected sizes for one upload path")
        current["kinds"].append(kind)

    for row in records["message_attachments"]:
        add(row.get("file_url"), row.get("file_size"), "message")
        add(row.get("thumbnail_url"), None, "message-thumbnail")
    for row in records["note_attachments"]:
        add(row.get("file_url"), row.get("file_size"), "note")
    for row in records["space_documents"]:
        if row.get("doc_type") == "document":
            add(row.get("url"), row.get("file_size"), "document")
    for row in records["document_images"]:
        add(row.get("file_path"), None, "document-image")

    def collect_embedded(value: Any) -> None:
        if isinstance(value, dict):
            for child in value.values():
                collect_embedded(child)
        elif isinstance(value, list):
            for child in value:
                collect_embedded(child)
        elif isinstance(value, str):
            for match in EMBEDDED_UPLOAD_RE.finditer(value):
                add(match.group(0), None, "embedded-reference")

    collect_embedded(records)
    if len(refs) != EXPECTED_FILE_COUNT:
        raise RuntimeError(f"expected {EXPECTED_FILE_COUNT} files, found {len(refs)}")
    return refs


class SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlparse(newurl)
        if parsed.scheme != "https" or parsed.hostname != ALLOWED_SOURCE_HOST:
            raise RuntimeError("download redirected away from allow-listed HTTPS host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def validate_file_magic(relative: str, data: bytes) -> str:
    suffix = PurePosixPath(relative).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "image/webp"
    if suffix == ".pptx" and data.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if "[Content_Types].xml" in archive.namelist() and any(
                    name.startswith("ppt/") for name in archive.namelist()
                ):
                    return (
                        "application/vnd.openxmlformats-officedocument."
                        "presentationml.presentation"
                    )
        except zipfile.BadZipFile:
            pass
    raise RuntimeError("downloaded file signature does not match its extension")


def download_files(
    bundle: Path, refs: Mapping[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    opener = urllib.request.build_opener(
        SafeRedirectHandler(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    manifest: list[dict[str, Any]] = []
    for relative in sorted(refs):
        target = bundle / "files" / Path(*PurePosixPath(relative).parts)
        _ensure_private_dir(target.parent)
        url = f"https://{ALLOWED_SOURCE_HOST}/uploads/{urllib.parse.quote(relative)}"
        request = urllib.request.Request(
            url, headers={"User-Agent": "uStudy-course-migration/1"}
        )
        with opener.open(request, timeout=60) as response:
            if response.status != 200:
                raise RuntimeError(f"file download failed with HTTP {response.status}")
            data = response.read()
            content_type = response.headers.get_content_type()
        detected_type = validate_file_magic(relative, data)
        expected_size = refs[relative].get("expected_size")
        if expected_size is not None and len(data) != int(expected_size):
            raise RuntimeError("downloaded file size differs from database metadata")
        target.write_bytes(data)
        try:
            os.chmod(target, 0o600)
        except OSError:
            if os.name != "nt":
                raise
        manifest.append(
            {
                "path": relative,
                "bytes": len(data),
                "sha256": sha256_bytes(data),
                "content_type": content_type,
                "detected_type": detected_type,
                "kinds": sorted(set(refs[relative]["kinds"])),
            }
        )
    return manifest


def _ensure_private_dir(path: Path) -> None:
    existed = path.exists()
    path.mkdir(parents=True, exist_ok=True)
    if not existed:
        try:
            os.chmod(path, 0o700)
        except OSError:
            if os.name != "nt":
                raise


def _safe_write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        if os.name != "nt":
            raise


def _atomic_write_private_json(path: Path, value: Any) -> None:
    _ensure_private_dir(path.parent)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        _safe_write_json(temporary, value)
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            if os.name != "nt":
                raise
        temporary.replace(path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            if os.name != "nt":
                raise
    finally:
        temporary.unlink(missing_ok=True)


def files_manifest_sha256(manifest: Mapping[str, Any]) -> str:
    return sha256_bytes(canonical_json(manifest["files"]).encode())


def validate_audit_identity(
    audit: Mapping[str, Any],
    manifest: Mapping[str, Any],
    teacher_id: UUID,
    *,
    statuses: set[str],
) -> None:
    expected = {
        "teacher_id": str(teacher_id),
        "target_user_id": str(EXAMPLE_USER_ID),
        "source_dump_sha256": EXPECTED_SOURCE_DUMP_SHA256,
        "records_sha256": manifest["records_sha256"],
        "files_manifest_sha256": files_manifest_sha256(manifest),
    }
    if audit.get("status") not in statuses or any(
        audit.get(key) != value for key, value in expected.items()
    ):
        raise RuntimeError("migration audit identity mismatch")
    system_member = audit.get("system_member_before") or {}
    teacher_member = audit.get("teacher_member_before") or {}
    if (
        audit.get("default_owner_before") != str(SYSTEM_USER_ID)
        or system_member.get("space_id") != str(DEFAULT_SPACE_ID)
        or system_member.get("user_id") != str(SYSTEM_USER_ID)
        or system_member.get("role") != "owner"
        or teacher_member.get("space_id") != str(DEFAULT_SPACE_ID)
        or teacher_member.get("user_id") != str(teacher_id)
        or teacher_member.get("role") not in {"teacher", "owner"}
        or audit.get("tables") != manifest.get("tables")
    ):
        raise RuntimeError("migration audit ownership snapshot mismatch")


async def export_bundle(
    dsn: str, bundle: Path, source_dump: Path | None
) -> dict[str, Any]:
    if bundle.exists() and any(bundle.iterdir()):
        raise RuntimeError("bundle directory must be empty")
    _ensure_private_dir(bundle)
    try:
        os.chmod(bundle, 0o700)
    except OSError:
        if os.name != "nt":
            raise
    if source_dump is None:
        raise RuntimeError("export requires the verified source dump path")
    digest = sha256_file(source_dump)
    if digest != EXPECTED_SOURCE_DUMP_SHA256:
        raise RuntimeError("source dump SHA-256 mismatch")
    conn = await connect(dsn)
    try:
        records = await export_records(conn)
    finally:
        await conn.close()
    validate_export(records)
    record_bytes = canonical_json(records).encode("utf-8")
    _safe_write_json(bundle / "records.json", records)
    files = download_files(bundle, collect_file_references(records))
    manifest = {
        "bundle_version": BUNDLE_VERSION,
        "source_dump_sha256": EXPECTED_SOURCE_DUMP_SHA256,
        "source_user_id": str(SOURCE_USER_ID),
        "source_spaces": EXPECTED_SPACE_NAMES,
        "records_sha256": sha256_bytes(record_bytes),
        "tables": {name: len(records[name]) for name in TABLE_ORDER},
        "files": files,
    }
    _safe_write_json(bundle / "manifest.json", manifest)
    return {"tables": manifest["tables"], "files": len(files), "bundle": str(bundle)}


def load_bundle(bundle: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    records = json.loads((bundle / "records.json").read_text(encoding="utf-8"))
    if manifest.get("bundle_version") != BUNDLE_VERSION:
        raise RuntimeError("unsupported bundle version")
    if manifest.get("source_dump_sha256") != EXPECTED_SOURCE_DUMP_SHA256:
        raise RuntimeError("bundle source identity mismatch")
    if sha256_bytes(canonical_json(records).encode("utf-8")) != manifest.get(
        "records_sha256"
    ):
        raise RuntimeError("records.json checksum mismatch")
    validate_export(records)
    for item in manifest.get("files", []):
        path = bundle / "files" / Path(*PurePosixPath(item["path"]).parts)
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or sha256_file(path) != item["sha256"]
        ):
            raise RuntimeError("bundle file checksum mismatch")
    if len(manifest.get("files", [])) != EXPECTED_FILE_COUNT:
        raise RuntimeError("bundle file count mismatch")
    return manifest, records


def sanitize_value(value: Any, target_user_id: UUID) -> Any:
    if isinstance(value, dict):
        return {
            key: sanitize_value(child, target_user_id)
            for key, child in value.items()
            if key.lower() not in SENSITIVE_JSON_KEYS
        }
    if isinstance(value, list):
        return [sanitize_value(child, target_user_id) for child in value]
    if isinstance(value, str):
        value = value.replace(str(SOURCE_USER_ID), str(target_user_id))
        value = re.sub(
            r"https://api\.ustudy\.cc(/uploads/)", r"\1", value, flags=re.IGNORECASE
        )
        value = re.sub(
            r"https://ustudy\.cc(/uploads/)", r"\1", value, flags=re.IGNORECASE
        )
        return value
    return value


def transform_records(
    records: Mapping[str, list[dict[str, Any]]],
    *,
    target_user_id: UUID,
    teacher_id: UUID,
) -> dict[str, list[dict[str, Any]]]:
    transformed: dict[str, list[dict[str, Any]]] = {}
    for table in TABLE_ORDER:
        transformed[table] = []
        for source in records[table]:
            row = sanitize_value(dict(source), target_user_id)
            if table == "spaces":
                row["user_id"] = str(teacher_id)
                row["is_collaborative"] = True
            elif table == "nodes":
                row["mastery"] = None
            elif table == "edges":
                row["user_id"] = (
                    str(target_user_id) if row.get("type") == "LEARNING_PATH" else None
                )
            elif table == "folders" or table == "notes":
                row["creator_user_id"] = str(target_user_id)
                row["visibility"] = "private"
            elif table == "conversations":
                row["user_id"] = str(target_user_id)
                row["kind"] = "learning"
            elif table == "messages":
                row["llm_context"] = None
            elif table == "message_attachments":
                row["user_id"] = str(target_user_id)
            elif table == "agent_tasks":
                row["user_id"] = str(target_user_id)
                if row.get("status") not in {"DONE", "FAILED"}:
                    raise RuntimeError("refusing to import non-terminal agent task")
            elif table == "quizzes":
                row["creator_user_id"] = str(target_user_id)
                row["visibility"] = "private"
            elif table in {
                "quiz_attempts",
                "node_user_mastery",
                "learning_path_events",
                "study_activity_logs",
                "review_schedules",
                "vector_memories",
                "calendar_events",
            }:
                row["user_id"] = str(target_user_id)
            elif table == "space_documents" and row.get("creator_user_id") == str(
                SOURCE_USER_ID
            ):
                row["creator_user_id"] = str(target_user_id)
            transformed[table].append(row)

    image_rows = transformed["document_images"]
    text_rows = transformed["document_texts"]
    for row in transformed["document_processing_tasks"]:
        document_id = row["document_id"]
        images = [item for item in image_rows if item["document_id"] == document_id]
        texts = [item for item in text_rows if item["document_id"] == document_id]
        page_numbers = [
            int(item["page_num"]) for item in images if item.get("page_num") is not None
        ]
        page_count = max(page_numbers) if page_numbers else len(texts)
        row.update(
            {
                "generation": 1,
                "stage": "completed",
                "processed_chunks": int(row.get("chunk_count") or 0),
                "page_count": page_count,
                "processed_pages": page_count,
                "asset_count": len(images),
                "attempt_count": 0,
                "available_at": row.get("completed_at") or row.get("created_at"),
                "lease_owner": None,
                "lease_token": None,
                "lease_expires_at": None,
                "error_code": None,
                "warning_code": None,
                "updated_at": row.get("completed_at") or row.get("created_at"),
            }
        )
    return transformed


def baseline_mastery_events(
    transformed: Mapping[str, list[dict[str, Any]]], target_user_id: UUID
) -> list[dict[str, Any]]:
    node_space = {row["id"]: row["space_id"] for row in transformed["nodes"]}
    events = []
    for row in transformed["node_user_mastery"]:
        events.append(
            {
                "id": str(uuid5(MIGRATION_NAMESPACE, f"mastery-baseline:{row['id']}")),
                "space_id": node_space[row["node_id"]],
                "node_id": row["node_id"],
                "user_id": str(target_user_id),
                "previous_mastery": None,
                "new_mastery": row["mastery"],
                "source": "baseline",
                "reason": "从 2026-07-22 生产备份迁移的掌握度基线",
                "created_at": row["updated_at"],
            }
        )
    return events


async def table_columns(conn: asyncpg.Connection, table: str) -> set[str]:
    rows = await conn.fetch(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        """,
        table,
    )
    return {row["column_name"] for row in rows}


async def validate_target_schema(conn: asyncpg.Connection) -> None:
    required = {
        "notes": {"visibility", "creator_user_id"},
        "quizzes": {"visibility", "creator_user_id"},
        "folders": {"visibility", "creator_user_id"},
        "conversations": {"kind"},
        "document_processing_tasks": {
            "generation",
            "stage",
            "page_count",
            "processed_pages",
            "asset_count",
            "attempt_count",
            "available_at",
            "lease_owner",
            "lease_token",
            "lease_expires_at",
            "error_code",
            "warning_code",
            "updated_at",
        },
        "node_mastery_events": {
            "space_id",
            "node_id",
            "user_id",
            "source",
            "reason",
        },
    }
    missing: dict[str, list[str]] = {}
    for table, names in required.items():
        absent = sorted(names - await table_columns(conn, table))
        if absent:
            missing[table] = absent
    if missing:
        raise RuntimeError(
            "target schema is not migration-ready: " + canonical_json(missing)
        )


async def insert_rows(
    conn: asyncpg.Connection, table: str, rows: list[dict[str, Any]]
) -> None:
    if not rows:
        return
    columns = await table_columns(conn, table)
    selected = [name for name in rows[0] if name in columns]
    if "id" not in selected:
        raise RuntimeError(f"{table} has no importable primary key")
    quoted = ", ".join(f'"{name}"' for name in selected)
    projection = ", ".join(f'r."{name}"' for name in selected)
    sql = (
        f'INSERT INTO public."{table}" ({quoted}) '
        f'SELECT {projection} FROM jsonb_populate_recordset(NULL::public."{table}", $1::jsonb) AS r'
    )
    await conn.execute(sql, [{key: row.get(key) for key in selected} for row in rows])


async def fetch_target_identity(
    conn: asyncpg.Connection, teacher_id: UUID, *, strict_roster: bool = True
) -> tuple[UUID, list[UUID]]:
    example_rows = await conn.fetch(
        "SELECT id FROM users WHERE lower(username) = 'example'"
    )
    if len(example_rows) != 1 or example_rows[0]["id"] != EXAMPLE_USER_ID:
        raise RuntimeError("target example identity mismatch")
    teacher_ok = await conn.fetchval(
        """
        SELECT EXISTS(
            SELECT 1 FROM spaces s
            LEFT JOIN space_members sm
              ON sm.space_id = s.id AND sm.user_id = $2
            WHERE s.id = $1
              AND (s.user_id = $2 OR sm.role::text = 'teacher')
        )
        """,
        DEFAULT_SPACE_ID,
        teacher_id,
    )
    if not teacher_ok or teacher_id in {EXAMPLE_USER_ID, SYSTEM_USER_ID}:
        raise RuntimeError(
            "target teacher identity is not authorized in the default course"
        )
    student_rows = await conn.fetch(
        """
        SELECT user_id FROM space_members
        WHERE space_id = $1 AND role::text = 'member'
        ORDER BY user_id
        """,
        DEFAULT_SPACE_ID,
    )
    students = [row["user_id"] for row in student_rows]
    if len(students) < EXPECTED_CURRENT_STUDENTS or EXAMPLE_USER_ID not in students:
        raise RuntimeError("target student roster mismatch")
    if strict_roster:
        roster_payload = (
            "\n".join(sorted(str(user_id) for user_id in students)) + "\n"
        ).encode()
        if (
            len(students) != EXPECTED_CURRENT_STUDENTS
            or sha256_bytes(roster_payload) != EXPECTED_STUDENT_ROSTER_SHA256
        ):
            raise RuntimeError("target student roster identity mismatch")
    return EXAMPLE_USER_ID, students


async def preflight_empty_target(
    conn: asyncpg.Connection,
    transformed: Mapping[str, list[dict[str, Any]]],
    baseline_events: list[dict[str, Any]],
) -> str:
    existing_spaces = await conn.fetch(
        "SELECT id, name FROM spaces WHERE id = ANY($1::uuid[])", list(SOURCE_SPACE_IDS)
    )
    if len(existing_spaces) == len(SOURCE_SPACE_IDS):
        return "already-present"
    if existing_spaces:
        raise RuntimeError("partial course import detected")
    name_collision = await conn.fetchval(
        "SELECT count(*) FROM spaces WHERE name = ANY($1::text[])",
        list(EXPECTED_SPACE_NAMES.values()),
    )
    if name_collision:
        raise RuntimeError("target contains a colliding course name")
    for table in TABLE_ORDER:
        ids = [UUID(row["id"]) for row in transformed[table] if row.get("id")]
        if ids and await conn.fetchval(
            f'SELECT count(*) FROM public."{table}" WHERE id = ANY($1::uuid[])', ids
        ):
            raise RuntimeError(f"target primary-key collision in {table}")
    event_ids = [UUID(row["id"]) for row in baseline_events]
    if event_ids and await conn.fetchval(
        "SELECT count(*) FROM node_mastery_events WHERE id = ANY($1::uuid[])", event_ids
    ):
        raise RuntimeError("target primary-key collision in node_mastery_events")
    return "empty"


def membership_id(space_id: UUID, user_id: UUID) -> UUID:
    return uuid5(MIGRATION_NAMESPACE, f"member:{space_id}:{user_id}")


async def insert_memberships(
    conn: asyncpg.Connection, teacher_id: UUID, students: list[UUID]
) -> None:
    rows = []
    for space_id in SOURCE_SPACE_IDS:
        rows.append(
            {
                "id": str(membership_id(space_id, teacher_id)),
                "space_id": str(space_id),
                "user_id": str(teacher_id),
                "role": "owner",
                "color": "#3B82F6",
                "can_edit_graph": True,
            }
        )
        for index, user_id in enumerate(students):
            rows.append(
                {
                    "id": str(membership_id(space_id, user_id)),
                    "space_id": str(space_id),
                    "user_id": str(user_id),
                    "role": "member",
                    "color": f"#{(0x1976D2 + index * 7919) & 0xFFFFFF:06X}",
                    "can_edit_graph": False,
                }
            )
    await insert_rows(conn, "space_members", rows)


async def default_owner_snapshot(
    conn: asyncpg.Connection, teacher_id: UUID, *, for_update: bool = False
) -> dict[str, Any]:
    before = await conn.fetchrow(
        "SELECT user_id FROM spaces WHERE id = $1"
        + (" FOR UPDATE" if for_update else ""),
        DEFAULT_SPACE_ID,
    )
    if before is None:
        raise RuntimeError("default course is missing")
    system_member_before = await conn.fetchval(
        "SELECT to_jsonb(sm) FROM space_members sm WHERE space_id = $1 AND user_id = $2",
        DEFAULT_SPACE_ID,
        SYSTEM_USER_ID,
    )
    teacher_member_before = await conn.fetchval(
        "SELECT to_jsonb(sm) FROM space_members sm WHERE space_id = $1 AND user_id = $2",
        DEFAULT_SPACE_ID,
        teacher_id,
    )
    if system_member_before is None or teacher_member_before is None:
        raise RuntimeError("default owner/teacher membership snapshot is incomplete")
    if (
        before["user_id"] != SYSTEM_USER_ID
        or system_member_before.get("role") != "owner"
        or teacher_member_before.get("role") != "teacher"
    ):
        raise RuntimeError("default course is not in the expected pre-migration state")
    return {
        "default_owner_before": str(before["user_id"]),
        "system_member_before": system_member_before,
        "teacher_member_before": teacher_member_before,
        "teacher_id": str(teacher_id),
    }


async def transfer_default_owner(
    conn: asyncpg.Connection,
    teacher_id: UUID,
    *,
    expected_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = await default_owner_snapshot(conn, teacher_id, for_update=True)
    if expected_snapshot is not None and comparable_json(snapshot) != comparable_json(
        expected_snapshot
    ):
        raise RuntimeError("default course ownership changed after preflight")
    await conn.execute(
        "UPDATE spaces SET user_id = $2 WHERE id = $1", DEFAULT_SPACE_ID, teacher_id
    )
    updated = await conn.execute(
        """
        UPDATE space_members SET role = 'owner', can_edit_graph = true
        WHERE space_id = $1 AND user_id = $2
        """,
        DEFAULT_SPACE_ID,
        teacher_id,
    )
    if updated != "UPDATE 1":
        raise RuntimeError("teacher membership is missing from the default course")
    await conn.execute(
        "DELETE FROM space_members WHERE space_id = $1 AND user_id = $2",
        DEFAULT_SPACE_ID,
        SYSTEM_USER_ID,
    )
    return snapshot


def plan_target_files(
    manifest: Mapping[str, Any], upload_root: Path
) -> tuple[list[Path], list[str]]:
    to_create: list[Path] = []
    reused: list[str] = []
    root = upload_root.resolve()
    for item in manifest["files"]:
        relative = PurePosixPath(item["path"])
        destination = (root / Path(*relative.parts)).resolve()
        if root not in destination.parents:
            raise RuntimeError("target upload path escaped the upload root")
        if destination.exists():
            if (
                destination.is_file()
                and destination.stat().st_size == item["bytes"]
                and sha256_file(destination) == item["sha256"]
            ):
                reused.append(item["path"])
                continue
            raise RuntimeError("target upload path exists with different content")
        to_create.append(destination)
    return to_create, reused


def stage_files(
    bundle: Path, manifest: Mapping[str, Any], upload_root: Path
) -> tuple[list[Path], list[str]]:
    created: list[Path] = []
    _, reused = plan_target_files(manifest, upload_root)
    root = upload_root.resolve()
    try:
        for item in manifest["files"]:
            relative = PurePosixPath(item["path"])
            source = bundle / "files" / Path(*relative.parts)
            destination = (root / Path(*relative.parts)).resolve()
            if root not in destination.parents:
                raise RuntimeError("target upload path escaped the upload root")
            if destination.exists():
                if (
                    destination.is_file()
                    and destination.stat().st_size == item["bytes"]
                    and sha256_file(destination) == item["sha256"]
                ):
                    continue
                raise RuntimeError("target upload path changed during staging")
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(
                f".{destination.name}.migration-{os.getpid()}-{uuid4().hex}.tmp"
            )
            shutil.copy2(source, temporary)
            if sha256_file(temporary) != item["sha256"]:
                temporary.unlink(missing_ok=True)
                raise RuntimeError("staged upload checksum mismatch")
            temporary.replace(destination)
            created.append(destination)
    except Exception:
        cleanup_created_files(created)
        raise
    return created, reused


def cleanup_created_files(paths: Iterable[Path]) -> None:
    for path in reversed(list(paths)):
        path.unlink(missing_ok=True)


def verify_target_files(manifest: Mapping[str, Any], upload_root: Path) -> None:
    root = upload_root.resolve()
    failures = 0
    for item in manifest["files"]:
        target = (root / Path(*PurePosixPath(item["path"]).parts)).resolve()
        if root not in target.parents:
            raise RuntimeError("target file escaped upload root")
        if (
            not target.is_file()
            or target.stat().st_size != item["bytes"]
            or sha256_file(target) != item["sha256"]
        ):
            failures += 1
    if failures:
        raise RuntimeError(f"target file verification failed for {failures} files")


async def verify_transformed_invariants(
    conn: asyncpg.Connection,
    records: Mapping[str, list[dict[str, Any]]],
    teacher_id: UUID,
) -> None:
    def ids(table: str) -> list[UUID]:
        return [UUID(row["id"]) for row in records[table]]

    checks = {
        "spaces": await conn.fetchval(
            """
            SELECT count(*) FROM spaces
            WHERE id=ANY($1::uuid[])
              AND (user_id<>$2 OR NOT is_collaborative
                   OR name<>CASE id
                       WHEN $3::uuid THEN '计算机网络'
                       WHEN $4::uuid THEN '计算机操作系统' END)
            """,
            ids("spaces"),
            teacher_id,
            NETWORK_SPACE_ID,
            OS_SPACE_ID,
        ),
        "nodes": await conn.fetchval(
            "SELECT count(*) FROM nodes WHERE id=ANY($1::uuid[]) AND mastery IS NOT NULL",
            ids("nodes"),
        ),
        "edges": await conn.fetchval(
            """
            SELECT count(*) FROM edges WHERE id=ANY($1::uuid[])
              AND ((type='LEARNING_PATH' AND user_id IS DISTINCT FROM $2)
                   OR (type<>'LEARNING_PATH' AND user_id IS NOT NULL))
            """,
            ids("edges"),
            EXAMPLE_USER_ID,
        ),
        "folders": await conn.fetchval(
            """
            SELECT count(*) FROM folders WHERE id=ANY($1::uuid[])
              AND (visibility<>'private' OR creator_user_id IS DISTINCT FROM $2)
            """,
            ids("folders"),
            EXAMPLE_USER_ID,
        ),
        "notes": await conn.fetchval(
            """
            SELECT count(*) FROM notes WHERE id=ANY($1::uuid[])
              AND (visibility<>'private' OR creator_user_id IS DISTINCT FROM $2)
            """,
            ids("notes"),
            EXAMPLE_USER_ID,
        ),
        "quizzes": await conn.fetchval(
            """
            SELECT count(*) FROM quizzes WHERE id=ANY($1::uuid[])
              AND (visibility<>'private' OR creator_user_id IS DISTINCT FROM $2)
            """,
            ids("quizzes"),
            EXAMPLE_USER_ID,
        ),
        "conversations": await conn.fetchval(
            """
            SELECT count(*) FROM conversations WHERE id=ANY($1::uuid[])
              AND (user_id IS DISTINCT FROM $2 OR kind<>'learning')
            """,
            ids("conversations"),
            EXAMPLE_USER_ID,
        ),
        "message_debug": await conn.fetchval(
            "SELECT count(*) FROM messages WHERE id=ANY($1::uuid[]) AND llm_context IS NOT NULL",
            ids("messages"),
        ),
        "message_attachments": await conn.fetchval(
            """
            SELECT count(*) FROM message_attachments
            WHERE id=ANY($1::uuid[]) AND user_id IS DISTINCT FROM $2
            """,
            ids("message_attachments"),
            EXAMPLE_USER_ID,
        ),
        "agent_tasks": await conn.fetchval(
            """
            SELECT count(*) FROM agent_tasks WHERE id=ANY($1::uuid[])
              AND (user_id IS DISTINCT FROM $2 OR status::text NOT IN ('DONE','FAILED'))
            """,
            ids("agent_tasks"),
            EXAMPLE_USER_ID,
        ),
        "personal_rows": await conn.fetchval(
            """
            SELECT
              (SELECT count(*) FROM quiz_attempts WHERE id=ANY($1::uuid[]) AND user_id IS DISTINCT FROM $6)
              +(SELECT count(*) FROM node_user_mastery WHERE id=ANY($2::uuid[]) AND user_id IS DISTINCT FROM $6)
              +(SELECT count(*) FROM learning_path_events WHERE id=ANY($3::uuid[]) AND user_id IS DISTINCT FROM $6)
              +(SELECT count(*) FROM study_activity_logs WHERE id=ANY($4::uuid[]) AND user_id IS DISTINCT FROM $6)
              +(SELECT count(*) FROM review_schedules WHERE id=ANY($5::uuid[]) AND user_id IS DISTINCT FROM $6)
            """,
            ids("quiz_attempts"),
            ids("node_user_mastery"),
            ids("learning_path_events"),
            ids("study_activity_logs"),
            ids("review_schedules"),
            EXAMPLE_USER_ID,
        ),
        "document_task": await conn.fetchval(
            """
            SELECT count(*) FROM document_processing_tasks
            WHERE id=ANY($1::uuid[])
              AND (status::text<>'completed' OR stage<>'completed'
                   OR generation<>1 OR lease_owner IS NOT NULL
                   OR lease_token IS NOT NULL OR lease_expires_at IS NOT NULL)
            """,
            ids("document_processing_tasks"),
        ),
    }
    failures = {name: int(count or 0) for name, count in checks.items() if count}
    if failures:
        raise RuntimeError(
            f"target transform invariant mismatch: {canonical_json(failures)}"
        )


async def verify_table_rows_exact(
    conn: asyncpg.Connection, table: str, expected_rows: list[dict[str, Any]]
) -> dict[str, int]:
    if not expected_rows:
        return {}
    columns = await table_columns(conn, table)
    target_rows = await conn.fetch(
        f'SELECT to_jsonb(t) AS data FROM public."{table}" t WHERE id=ANY($1::uuid[])',
        [UUID(row["id"]) for row in expected_rows],
    )
    target_by_id = {row["data"]["id"]: row["data"] for row in target_rows}
    mismatches: dict[str, int] = {}
    for expected in expected_rows:
        actual = target_by_id.get(expected["id"])
        if actual is None:
            mismatches["<missing>"] = mismatches.get("<missing>", 0) + 1
            continue
        for key, value in expected.items():
            if key not in columns:
                continue
            if comparable_json(actual.get(key)) != comparable_json(value):
                mismatches[key] = mismatches.get(key, 0) + 1
    return mismatches


async def verify_expected_rows_exact(
    conn: asyncpg.Connection,
    records: Mapping[str, list[dict[str, Any]]],
) -> None:
    mismatches = {
        table: table_mismatches
        for table in TABLE_ORDER
        if (
            table_mismatches := await verify_table_rows_exact(
                conn, table, records[table]
            )
        )
    }
    if mismatches:
        raise RuntimeError(
            "target row content differs from bundle: " + canonical_json(mismatches)
        )


async def verify_imported(
    conn: asyncpg.Connection,
    teacher_id: UUID,
    *,
    strict_counts: bool = True,
    expected_records: Mapping[str, list[dict[str, Any]]] | None = None,
    expected_baseline_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    spaces = await conn.fetch(
        """
        SELECT s.id, s.name, s.user_id,
               count(*) FILTER (WHERE sm.role::text = 'owner') AS owners,
               count(*) FILTER (WHERE sm.role::text = 'member') AS students
        FROM spaces s LEFT JOIN space_members sm ON sm.space_id = s.id
        WHERE s.id = ANY($1::uuid[])
        GROUP BY s.id, s.name, s.user_id ORDER BY s.id
        """,
        [DEFAULT_SPACE_ID, *SOURCE_SPACE_IDS],
    )
    if len(spaces) != 3:
        raise RuntimeError("managed course count mismatch")
    for row in spaces:
        if row["user_id"] != teacher_id or row["owners"] != 1:
            raise RuntimeError("managed course owner invariant failed")
        if strict_counts and row["students"] < EXPECTED_CURRENT_STUDENTS:
            raise RuntimeError("managed course student roster is incomplete")
    membership_rows = await conn.fetch(
        """
        SELECT space_id, role::text AS role, user_id, can_edit_graph
        FROM space_members WHERE space_id=ANY($1::uuid[])
        """,
        [DEFAULT_SPACE_ID, *SOURCE_SPACE_IDS],
    )
    member_sets = {
        space_id: {
            row["user_id"]
            for row in membership_rows
            if row["space_id"] == space_id and row["role"] == "member"
        }
        for space_id in (DEFAULT_SPACE_ID, *SOURCE_SPACE_IDS)
    }
    if any(
        members != member_sets[DEFAULT_SPACE_ID] for members in member_sets.values()
    ):
        raise RuntimeError("managed course student rosters differ")
    for space_id in (DEFAULT_SPACE_ID, *SOURCE_SPACE_IDS):
        owner_rows = [
            row
            for row in membership_rows
            if row["space_id"] == space_id and row["role"] == "owner"
        ]
        if (
            len(owner_rows) != 1
            or owner_rows[0]["user_id"] != teacher_id
            or not owner_rows[0]["can_edit_graph"]
        ):
            raise RuntimeError("managed course owner membership mismatch")
        if any(
            row["space_id"] == space_id and row["user_id"] == SYSTEM_USER_ID
            for row in membership_rows
        ):
            raise RuntimeError("system user remains a managed course member")

    counts: dict[str, int] = {}
    for table in TABLE_ORDER:
        if expected_records is not None:
            expected_ids = [UUID(row["id"]) for row in expected_records[table]]
            count = (
                await conn.fetchval(
                    f'SELECT count(*) FROM public."{table}" WHERE id = ANY($1::uuid[])',
                    expected_ids,
                )
                if expected_ids
                else 0
            )
            counts[table] = int(count or 0)
            continue
        columns = await table_columns(conn, table)
        if table == "spaces":
            count = await conn.fetchval(
                "SELECT count(*) FROM spaces WHERE id = ANY($1::uuid[])",
                list(SOURCE_SPACE_IDS),
            )
        elif "space_id" in columns:
            count = await conn.fetchval(
                f'SELECT count(*) FROM public."{table}" WHERE space_id = ANY($1::uuid[])',
                list(SOURCE_SPACE_IDS),
            )
        elif table in {"messages", "conversation_agent_todos"}:
            fk = "conversation_id"
            count = await conn.fetchval(
                f"""
                SELECT count(*) FROM public."{table}" x
                JOIN conversations c ON c.id = x.{fk}
                WHERE c.space_id = ANY($1::uuid[]) AND c.user_id = $2
                """,
                list(SOURCE_SPACE_IDS),
                EXAMPLE_USER_ID,
            )
        elif table == "message_attachments":
            count = await conn.fetchval(
                """
                SELECT count(*) FROM message_attachments a
                JOIN messages m ON m.id = a.message_id
                JOIN conversations c ON c.id = m.conversation_id
                WHERE c.space_id = ANY($1::uuid[]) AND c.user_id = $2
                """,
                list(SOURCE_SPACE_IDS),
                EXAMPLE_USER_ID,
            )
        elif table == "note_attachments":
            count = await conn.fetchval(
                """
                SELECT count(*) FROM note_attachments a JOIN notes n ON n.id = a.note_id
                WHERE n.space_id = ANY($1::uuid[]) AND n.creator_user_id = $2
                """,
                list(SOURCE_SPACE_IDS),
                EXAMPLE_USER_ID,
            )
        elif table == "questions":
            count = await conn.fetchval(
                """
                SELECT count(*) FROM questions q JOIN quizzes z ON z.id = q.quiz_id
                WHERE z.space_id = ANY($1::uuid[])
                """,
                list(SOURCE_SPACE_IDS),
            )
        elif table == "quiz_attempts":
            count = await conn.fetchval(
                """
                SELECT count(*) FROM quiz_attempts a JOIN quizzes q ON q.id = a.quiz_id
                WHERE q.space_id = ANY($1::uuid[]) AND a.user_id = $2
                """,
                list(SOURCE_SPACE_IDS),
                EXAMPLE_USER_ID,
            )
        elif table == "node_user_mastery":
            count = await conn.fetchval(
                """
                SELECT count(*) FROM node_user_mastery m JOIN nodes n ON n.id = m.node_id
                WHERE n.space_id = ANY($1::uuid[]) AND m.user_id = $2
                """,
                list(SOURCE_SPACE_IDS),
                EXAMPLE_USER_ID,
            )
        elif table == "review_schedules":
            count = await conn.fetchval(
                """
                SELECT count(*) FROM review_schedules r
                JOIN study_activity_logs a ON a.id = r.activity_id
                WHERE a.space_id = ANY($1::uuid[]) AND r.user_id = $2
                """,
                list(SOURCE_SPACE_IDS),
                EXAMPLE_USER_ID,
            )
        elif table.startswith("document_"):
            count = await conn.fetchval(
                f"""
                SELECT count(*) FROM public."{table}" x
                JOIN space_documents d ON d.id = x.document_id
                WHERE d.space_id = ANY($1::uuid[])
                """,
                list(SOURCE_SPACE_IDS),
            )
        elif table == "calendar_events":
            count = await conn.fetchval(
                """
                SELECT count(*) FROM calendar_events e JOIN conversations c ON c.id=e.source_conversation_id
                WHERE c.space_id = ANY($1::uuid[]) AND e.user_id=$2
                """,
                list(SOURCE_SPACE_IDS),
                EXAMPLE_USER_ID,
            )
        else:
            count = 0
        counts[table] = int(count or 0)
    if strict_counts:
        for table, expected in EXPECTED_TABLE_COUNTS.items():
            if counts[table] != expected:
                raise RuntimeError(
                    f"target count mismatch for {table}: {counts[table]} != {expected}"
                )
        event_ids = (
            [UUID(row["id"]) for row in expected_baseline_events]
            if expected_baseline_events is not None
            else [
                uuid5(MIGRATION_NAMESPACE, f"mastery-baseline:{row_id}")
                for row_id in await conn.fetchval(
                    """
                    SELECT coalesce(array_agg(m.id), ARRAY[]::uuid[])
                    FROM node_user_mastery m JOIN nodes n ON n.id=m.node_id
                    WHERE n.space_id=ANY($1::uuid[]) AND m.user_id=$2
                    """,
                    list(SOURCE_SPACE_IDS),
                    EXAMPLE_USER_ID,
                )
            ]
        )
        baseline_count = await conn.fetchval(
            """
            SELECT count(*) FROM node_mastery_events
            WHERE id = ANY($1::uuid[])
            """,
            event_ids,
        )
        if baseline_count != EXPECTED_TABLE_COUNTS["node_user_mastery"]:
            raise RuntimeError("mastery baseline event count mismatch")
        if expected_baseline_events is not None:
            baseline_mismatches = await verify_table_rows_exact(
                conn, "node_mastery_events", expected_baseline_events
            )
            if baseline_mismatches:
                raise RuntimeError(
                    "mastery baseline content mismatch: "
                    + canonical_json(baseline_mismatches)
                )
    if expected_records is not None:
        await verify_transformed_invariants(conn, expected_records, teacher_id)
        await verify_expected_rows_exact(conn, expected_records)
    return {"spaces": len(spaces), "counts": counts}


async def import_bundle(
    dsn: str,
    bundle: Path,
    upload_root: Path,
    teacher_id: UUID,
    *,
    execute: bool,
    audit_output: Path | None,
) -> dict[str, Any]:
    manifest, source_records = load_bundle(bundle)
    transformed = transform_records(
        source_records, target_user_id=EXAMPLE_USER_ID, teacher_id=teacher_id
    )
    baseline_events = baseline_mastery_events(transformed, EXAMPLE_USER_ID)
    conn = await connect(dsn)
    created_files: list[Path] = []
    database_committed = False
    prepared_audit: dict[str, Any] | None = None
    lock_acquired = False
    try:
        await conn.execute("SELECT pg_advisory_lock($1)", ADVISORY_LOCK_KEY)
        lock_acquired = True
        await validate_target_schema(conn)
        state = await preflight_empty_target(conn, transformed, baseline_events)
        if state == "already-present":
            _, students = await fetch_target_identity(
                conn, teacher_id, strict_roster=False
            )
            result = await verify_imported(
                conn,
                teacher_id,
                expected_records=transformed,
                expected_baseline_events=baseline_events,
            )
            verify_target_files(manifest, upload_root)
            if audit_output is None or not audit_output.is_file():
                raise RuntimeError("an applied import requires its audit file")
            applied_audit = json.loads(audit_output.read_text(encoding="utf-8"))
            validate_audit_identity(
                applied_audit,
                manifest,
                teacher_id,
                statuses={"prepared", "applied", "unknown"},
            )
            if applied_audit["status"] != "applied":
                applied_audit["status"] = "applied"
                applied_audit["applied_at"] = datetime.now().astimezone().isoformat()
                _atomic_write_private_json(audit_output, applied_audit)
            return {"status": "already-applied", **result}
        _, students = await fetch_target_identity(conn, teacher_id)
        if not execute:
            planned_files, reused_files = plan_target_files(manifest, upload_root)
            return {
                "status": "dry-run-ok",
                "tables": {name: len(rows) for name, rows in transformed.items()},
                "mastery_baselines": len(baseline_events),
                "students": len(students),
                "files": len(manifest["files"]),
                "files_to_create": len(planned_files),
                "files_to_reuse": len(reused_files),
            }
        if audit_output is None:
            raise RuntimeError("executing an import requires --audit-output")
        owner_snapshot = await default_owner_snapshot(conn, teacher_id)
        planned_created, planned_reused = plan_target_files(manifest, upload_root)
        resume_audit: dict[str, Any] | None = None
        if audit_output.is_file():
            candidate = json.loads(audit_output.read_text(encoding="utf-8"))
            if candidate.get("status") in {"prepared", "unknown", "aborted"}:
                validate_audit_identity(
                    candidate,
                    manifest,
                    teacher_id,
                    statuses={"prepared", "unknown", "aborted"},
                )
                if comparable_json(
                    {
                        key: candidate[key]
                        for key in (
                            "default_owner_before",
                            "system_member_before",
                            "teacher_member_before",
                            "teacher_id",
                        )
                    }
                ) != comparable_json(owner_snapshot):
                    raise RuntimeError("prepared audit owner snapshot mismatch")
                resume_audit = candidate
            elif candidate.get("status") == "applied":
                raise RuntimeError("audit says applied but target courses are absent")

        if resume_audit is None:
            created_files = planned_created
            prepared_audit = {
                "status": "prepared",
                "prepared_at": datetime.now().astimezone().isoformat(),
                "teacher_id": str(teacher_id),
                "target_user_id": str(EXAMPLE_USER_ID),
                "source_dump_sha256": EXPECTED_SOURCE_DUMP_SHA256,
                "records_sha256": manifest["records_sha256"],
                "files_manifest_sha256": files_manifest_sha256(manifest),
                "files_created": len(created_files),
                "file_paths_created": [
                    path.relative_to(upload_root.resolve()).as_posix()
                    for path in created_files
                ],
                "files_reused": len(planned_reused),
                "file_paths_reused": planned_reused,
                "tables": manifest["tables"],
                **owner_snapshot,
            }
            _atomic_write_private_json(audit_output, prepared_audit)
        else:
            prepared_audit = resume_audit
            owned_paths = [
                PurePosixPath(value)
                for value in prepared_audit.get("file_paths_created", [])
            ]
            reused_paths = set(prepared_audit.get("file_paths_reused", []))
            all_paths = {item["path"] for item in manifest["files"]}
            if {path.as_posix() for path in owned_paths} | reused_paths != all_paths:
                raise RuntimeError("prepared audit file ownership is incomplete")
            root = upload_root.resolve()
            for reused_path in list(reused_paths):
                relative = PurePosixPath(reused_path)
                target = (root / Path(*relative.parts)).resolve()
                if not target.exists():
                    reused_paths.remove(reused_path)
                    owned_paths.append(relative)
            created_files = [
                (root / Path(*path.parts)).resolve() for path in owned_paths
            ]
            prepared_audit["status"] = "prepared"
            prepared_audit["resumed_at"] = datetime.now().astimezone().isoformat()
            prepared_audit["file_paths_created"] = [
                path.as_posix() for path in owned_paths
            ]
            prepared_audit["files_created"] = len(owned_paths)
            prepared_audit["file_paths_reused"] = sorted(reused_paths)
            prepared_audit["files_reused"] = len(reused_paths)
            _atomic_write_private_json(audit_output, prepared_audit)

        staged_now, _ = stage_files(bundle, manifest, upload_root)
        owned_set = {path.resolve() for path in created_files}
        if any(path.resolve() not in owned_set for path in staged_now):
            cleanup_created_files(staged_now)
            raise RuntimeError("staging created a file not owned by the prepared audit")
        verify_target_files(manifest, upload_root)
        async with conn.transaction(isolation="serializable"):
            if (
                await preflight_empty_target(conn, transformed, baseline_events)
                != "empty"
            ):
                raise RuntimeError("target changed after preflight")
            await transfer_default_owner(
                conn, teacher_id, expected_snapshot=owner_snapshot
            )
            for table in TABLE_ORDER:
                await insert_rows(conn, table, transformed[table])
            await insert_rows(conn, "node_mastery_events", baseline_events)
            await insert_memberships(conn, teacher_id, students)
            await verify_imported(
                conn,
                teacher_id,
                expected_records=transformed,
                expected_baseline_events=baseline_events,
            )
        database_committed = True
        prepared_audit["status"] = "applied"
        prepared_audit["applied_at"] = datetime.now().astimezone().isoformat()
        _atomic_write_private_json(audit_output, prepared_audit)
        return prepared_audit
    except Exception:
        if not database_committed and prepared_audit is not None:
            recovery_conn = conn
            close_recovery_conn = False
            try:
                if conn.is_closed():
                    recovery_conn = await connect(dsn)
                    close_recovery_conn = True
                    await recovery_conn.execute(
                        "SELECT pg_advisory_lock($1)", ADVISORY_LOCK_KEY
                    )
                recovery_state = await preflight_empty_target(
                    recovery_conn, transformed, baseline_events
                )
                if recovery_state == "already-present":
                    await verify_imported(
                        recovery_conn,
                        teacher_id,
                        expected_records=transformed,
                        expected_baseline_events=baseline_events,
                    )
                    verify_target_files(manifest, upload_root)
                    prepared_audit["status"] = "applied"
                    prepared_audit["applied_at"] = (
                        datetime.now().astimezone().isoformat()
                    )
                    prepared_audit["recovered_after_uncertain_commit"] = True
                    if audit_output is not None:
                        _atomic_write_private_json(audit_output, prepared_audit)
                    return prepared_audit
                if recovery_state == "empty":
                    cleanup_created_files(created_files)
                    prepared_audit["status"] = "aborted"
                else:
                    prepared_audit["status"] = "unknown"
                if audit_output is not None:
                    _atomic_write_private_json(audit_output, prepared_audit)
            except Exception:  # noqa: BLE001 - any recovery failure must preserve files
                prepared_audit["status"] = "unknown"
                if audit_output is not None:
                    try:
                        _atomic_write_private_json(audit_output, prepared_audit)
                    except OSError:
                        pass
            finally:
                if close_recovery_conn:
                    try:
                        await recovery_conn.execute(
                            "SELECT pg_advisory_unlock($1)", ADVISORY_LOCK_KEY
                        )
                    finally:
                        await recovery_conn.close()
        raise
    finally:
        if lock_acquired and not conn.is_closed():
            await conn.execute("SELECT pg_advisory_unlock($1)", ADVISORY_LOCK_KEY)
        await conn.close()


async def rollback_import(
    dsn: str,
    bundle: Path,
    upload_root: Path,
    teacher_id: UUID,
    audit_path: Path,
    *,
    execute: bool,
) -> dict[str, Any]:
    manifest, source_records = load_bundle(bundle)
    transformed = transform_records(
        source_records, target_user_id=EXAMPLE_USER_ID, teacher_id=teacher_id
    )
    baseline_events = baseline_mastery_events(transformed, EXAMPLE_USER_ID)
    if not audit_path.is_file():
        raise RuntimeError("rollback requires the applied audit file")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    validate_audit_identity(
        audit,
        manifest,
        teacher_id,
        statuses={"prepared", "applied", "unknown", "rolled-back"},
    )
    created_paths = [
        PurePosixPath(value) for value in audit.get("file_paths_created", [])
    ]
    expected_files = {item["path"]: item for item in manifest["files"]}
    for relative in created_paths:
        if relative.as_posix() not in expected_files or ".." in relative.parts:
            raise RuntimeError("rollback audit contains an unsafe file path")
    root = upload_root.resolve()
    mismatched_files = 0
    for relative in created_paths:
        target = (root / Path(*relative.parts)).resolve()
        if root not in target.parents:
            raise RuntimeError("rollback file escaped upload root")
        if target.exists() and (
            not target.is_file()
            or sha256_file(target) != expected_files[relative.as_posix()]["sha256"]
        ):
            mismatched_files += 1
    if mismatched_files:
        raise RuntimeError(
            f"refusing rollback because {mismatched_files} created files changed"
        )
    conn = await connect(dsn)
    lock_acquired = False
    try:
        await conn.execute("SELECT pg_advisory_lock($1)", ADVISORY_LOCK_KEY)
        lock_acquired = True
        await validate_target_schema(conn)
        expected_ids = {
            table: [UUID(row["id"]) for row in source_records[table]]
            for table in TABLE_ORDER
        }
        expected_ids["node_mastery_events"] = [
            uuid5(MIGRATION_NAMESPACE, f"mastery-baseline:{row['id']}")
            for row in source_records["node_user_mastery"]
        ]
        unexpected: dict[str, int] = {}
        direct_tables = await conn.fetch(
            """
            SELECT c.table_name
            FROM information_schema.columns c
            JOIN information_schema.columns i
              ON i.table_schema=c.table_schema AND i.table_name=c.table_name
             AND i.column_name='id'
            WHERE c.table_schema='public' AND c.column_name='space_id'
            GROUP BY c.table_name ORDER BY c.table_name
            """
        )
        for row in direct_tables:
            table = row["table_name"]
            if table in {"spaces", "space_members"}:
                continue
            allowed = expected_ids.get(table, [])
            count = await conn.fetchval(
                f'SELECT count(*) FROM public."{table}" '
                "WHERE space_id=ANY($1::uuid[]) "
                "AND (cardinality($2::uuid[])=0 OR NOT (id=ANY($2::uuid[])))",
                list(SOURCE_SPACE_IDS),
                allowed,
            )
            if count:
                unexpected[table] = int(count)

        indirect_checks = {
            "messages": (
                "SELECT count(*) FROM messages x JOIN conversations p ON p.id=x.conversation_id "
                "WHERE p.space_id=ANY($1::uuid[]) AND NOT (x.id=ANY($2::uuid[]))"
            ),
            "conversation_agent_todos": (
                "SELECT count(*) FROM conversation_agent_todos x JOIN conversations p ON p.id=x.conversation_id "
                "WHERE p.space_id=ANY($1::uuid[]) AND NOT (x.id=ANY($2::uuid[]))"
            ),
            "message_attachments": (
                "SELECT count(*) FROM message_attachments x JOIN messages m ON m.id=x.message_id "
                "JOIN conversations p ON p.id=m.conversation_id "
                "WHERE p.space_id=ANY($1::uuid[]) AND NOT (x.id=ANY($2::uuid[]))"
            ),
            "note_attachments": (
                "SELECT count(*) FROM note_attachments x JOIN notes p ON p.id=x.note_id "
                "WHERE p.space_id=ANY($1::uuid[]) AND NOT (x.id=ANY($2::uuid[]))"
            ),
            "questions": (
                "SELECT count(*) FROM questions x JOIN quizzes p ON p.id=x.quiz_id "
                "WHERE p.space_id=ANY($1::uuid[]) AND NOT (x.id=ANY($2::uuid[]))"
            ),
            "quiz_attempts": (
                "SELECT count(*) FROM quiz_attempts x JOIN quizzes p ON p.id=x.quiz_id "
                "WHERE p.space_id=ANY($1::uuid[]) AND NOT (x.id=ANY($2::uuid[]))"
            ),
            "node_user_mastery": (
                "SELECT count(*) FROM node_user_mastery x JOIN nodes p ON p.id=x.node_id "
                "WHERE p.space_id=ANY($1::uuid[]) AND NOT (x.id=ANY($2::uuid[]))"
            ),
            "review_schedules": (
                "SELECT count(*) FROM review_schedules x JOIN study_activity_logs p ON p.id=x.activity_id "
                "WHERE p.space_id=ANY($1::uuid[]) AND NOT (x.id=ANY($2::uuid[]))"
            ),
            "document_processing_tasks": (
                "SELECT count(*) FROM document_processing_tasks x JOIN space_documents p ON p.id=x.document_id "
                "WHERE p.space_id=ANY($1::uuid[]) AND NOT (x.id=ANY($2::uuid[]))"
            ),
            "calendar_events": (
                "SELECT count(*) FROM calendar_events x JOIN conversations p ON p.id=x.source_conversation_id "
                "WHERE p.space_id=ANY($1::uuid[]) AND NOT (x.id=ANY($2::uuid[]))"
            ),
        }
        for table, sql in indirect_checks.items():
            allowed = expected_ids.get(table, [])
            count = await conn.fetchval(sql, list(SOURCE_SPACE_IDS), allowed)
            if count:
                unexpected[table] = int(count)
        if unexpected:
            raise RuntimeError(
                "rollback would delete post-import data: " + canonical_json(unexpected)
            )
        target_state = await preflight_empty_target(
            conn,
            transformed,
            baseline_events,
        )
        if not execute:
            return {
                "status": "rollback-dry-run-ok",
                "target_state": target_state,
                "tables": {name: len(source_records[name]) for name in TABLE_ORDER},
                "files_to_delete": len(created_paths),
                "unexpected_rows": 0,
            }
        # Re-check under the same lock used by imports before changing the DB.
        for relative in created_paths:
            target = (root / Path(*relative.parts)).resolve()
            if target.exists() and (
                not target.is_file()
                or sha256_file(target) != expected_files[relative.as_posix()]["sha256"]
            ):
                raise RuntimeError("a created migration file changed before rollback")
        async with conn.transaction(isolation="serializable"):
            for table in reversed(TABLE_ORDER):
                ids = [
                    UUID(row["id"]) for row in source_records[table] if row.get("id")
                ]
                if ids:
                    await conn.execute(
                        f'DELETE FROM public."{table}" WHERE id = ANY($1::uuid[])',
                        ids,
                    )
            event_ids = [
                uuid5(MIGRATION_NAMESPACE, f"mastery-baseline:{row['id']}")
                for row in source_records["node_user_mastery"]
            ]
            if event_ids:
                await conn.execute(
                    "DELETE FROM node_mastery_events WHERE id = ANY($1::uuid[])",
                    event_ids,
                )
            await conn.execute(
                "UPDATE spaces SET user_id = $2 WHERE id = $1",
                DEFAULT_SPACE_ID,
                UUID(audit["default_owner_before"]),
            )
            await conn.execute(
                "DELETE FROM space_members WHERE space_id=$1 AND user_id=ANY($2::uuid[])",
                DEFAULT_SPACE_ID,
                [teacher_id, SYSTEM_USER_ID],
            )
            await insert_rows(
                conn,
                "space_members",
                [audit["system_member_before"], audit["teacher_member_before"]],
            )
            remaining = await conn.fetchval(
                "SELECT count(*) FROM spaces WHERE id = ANY($1::uuid[])",
                list(SOURCE_SPACE_IDS),
            )
            if remaining:
                raise RuntimeError("rollback left imported courses behind")

        deleted = 0
        already_missing = 0
        for relative in created_paths:
            target = (root / Path(*relative.parts)).resolve()
            if target.is_file():
                target.unlink()
                deleted += 1
            else:
                already_missing += 1
        audit["status"] = "rolled-back"
        audit["rolled_back_at"] = datetime.now().astimezone().isoformat()
        _atomic_write_private_json(audit_path, audit)
        return {
            "status": "rolled-back",
            "files_deleted": deleted,
            "files_already_missing": already_missing,
        }
    finally:
        if lock_acquired and not conn.is_closed():
            await conn.execute("SELECT pg_advisory_unlock($1)", ADVISORY_LOCK_KEY)
        await conn.close()


async def verify_command(
    dsn: str, bundle: Path, upload_root: Path, teacher_id: UUID
) -> dict[str, Any]:
    manifest, source_records = load_bundle(bundle)
    verify_target_files(manifest, upload_root)
    conn = await connect(dsn)
    try:
        await validate_target_schema(conn)
        transformed = transform_records(
            source_records, target_user_id=EXAMPLE_USER_ID, teacher_id=teacher_id
        )
        baseline_events = baseline_mastery_events(transformed, EXAMPLE_USER_ID)
        return await verify_imported(
            conn,
            teacher_id,
            expected_records=transformed,
            expected_baseline_events=baseline_events,
        )
    finally:
        await conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("export", "import", "verify", "rollback"))
    parser.add_argument("bundle", type=Path)
    parser.add_argument(
        "--dsn",
        default=os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL"),
        help="Database URL; defaults to MIGRATION_DATABASE_URL or DATABASE_URL",
    )
    parser.add_argument("--source-dump", type=Path)
    parser.add_argument("--upload-root", type=Path, default=Path("/app/uploads"))
    parser.add_argument("--teacher-id", type=UUID)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.dsn:
        parser.error("--dsn or a database URL environment variable is required")
    if args.command == "export" and args.source_dump is None:
        parser.error("--source-dump is required for export")
    if args.command in {"import", "verify", "rollback"} and args.teacher_id is None:
        parser.error("--teacher-id is required for import, verify, and rollback")
    if args.command == "import" and args.execute and args.audit_output is None:
        parser.error("--audit-output is required when import uses --execute")
    if args.command == "rollback" and args.audit_output is None:
        parser.error("--audit-output must point to the applied audit for rollback")
    return args


async def async_main() -> None:
    args = parse_args()
    if args.command == "export":
        result = await export_bundle(args.dsn, args.bundle, args.source_dump)
    elif args.command == "import":
        result = await import_bundle(
            args.dsn,
            args.bundle,
            args.upload_root,
            args.teacher_id,
            execute=args.execute,
            audit_output=args.audit_output,
        )
    elif args.command == "verify":
        result = await verify_command(
            args.dsn, args.bundle, args.upload_root, args.teacher_id
        )
    else:
        result = await rollback_import(
            args.dsn,
            args.bundle,
            args.upload_root,
            args.teacher_id,
            args.audit_output,
            execute=args.execute,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except Exception as exc:  # Keep logs free of row contents and credentials.
        print(f"migration failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
