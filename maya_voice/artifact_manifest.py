from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import aiosqlite

from maya_voice.work_runtime import current_voice_work_db_path, current_voice_work_id


MANIFEST_TABLE = "voice_artifact_manifests"
RENDER_REPORT_TABLE = "voice_artifact_render_reports"


async def init_artifact_manifest_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {MANIFEST_TABLE} (
                work_id TEXT PRIMARY KEY,
                manifest_version INTEGER NOT NULL DEFAULT 1,
                artifact_type TEXT DEFAULT '',
                title TEXT DEFAULT '',
                topic TEXT DEFAULT '',
                audience TEXT DEFAULT '',
                request TEXT DEFAULT '',
                structured_intent_json TEXT DEFAULT '{{}}',
                source_turn_ids_json TEXT DEFAULT '[]',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {RENDER_REPORT_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                work_id TEXT NOT NULL,
                manifest_version_used INTEGER NOT NULL,
                artifact_path TEXT DEFAULT '',
                sha256 TEXT DEFAULT '',
                fields_rendered_json TEXT DEFAULT '{{}}',
                sections_created_json TEXT DEFAULT '[]',
                status TEXT DEFAULT 'ok',
                reason_code TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def create_or_get_manifest(
    db_path: str,
    work_id: str,
    *,
    request: str,
    args: dict[str, Any] | None = None,
    kind: str = "",
) -> dict[str, Any]:
    if not work_id:
        return {}
    await init_artifact_manifest_db(db_path)
    existing = await get_manifest(db_path, work_id)
    if existing:
        return existing
    args = dict(args or {})
    title = _clean_title(str(args.get("title") or args.get("artifact_title") or ""))
    topic = str(args.get("topic") or args.get("artifact_topic") or "").strip()
    artifact_type = str(args.get("artifact_type") or "").strip()
    if artifact_type == "auto":
        artifact_type = ""
    intent = _structured_intent(args, request=request, kind=kind)
    if not title:
        title = _clean_title(topic or request)
    if not topic:
        topic = request.strip()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            INSERT INTO {MANIFEST_TABLE}
                (work_id, manifest_version, artifact_type, title, topic, audience, request,
                 structured_intent_json, source_turn_ids_json)
            VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                work_id,
                artifact_type,
                title,
                topic,
                str(args.get("audience") or "").strip(),
                request.strip(),
                json.dumps(intent, sort_keys=True),
                json.dumps(_string_list(args.get("source_turn_ids"))),
            ),
        )
        await db.commit()
    return await get_manifest(db_path, work_id) or {}


async def create_metadata_only_manifest(
    db_path: str,
    work_id: str,
    *,
    artifact_path: str,
    artifact_type: str = "",
    title: str = "",
    request: str = "",
) -> dict[str, Any]:
    """Create a manifest for legacy artifacts from metadata only.

    This deliberately does not read or parse the artifact body. Semantic fields
    stay unset unless Maya supplies them later through a manifest patch.
    """

    if not work_id:
        return {}
    await init_artifact_manifest_db(db_path)
    existing = await get_manifest(db_path, work_id)
    if existing:
        return existing
    path = Path(artifact_path)
    clean_type = artifact_type.strip() or path.suffix.lower().lstrip(".")
    clean_title = _clean_title(title or path.stem.replace("-", " ").replace("_", " "))
    intent = {
        "metadata_only": True,
        "artifact_path": str(path),
    }
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            INSERT INTO {MANIFEST_TABLE}
                (work_id, manifest_version, artifact_type, title, topic, audience, request,
                 structured_intent_json, source_turn_ids_json)
            VALUES (?, 1, ?, ?, '', '', ?, ?, '[]')
            """,
            (
                work_id,
                clean_type,
                clean_title,
                request.strip(),
                json.dumps(intent, sort_keys=True),
            ),
        )
        await db.commit()
    return await get_manifest(db_path, work_id) or {}


async def get_manifest(db_path: str, work_id: str) -> dict[str, Any] | None:
    if not db_path or not work_id:
        return None
    await init_artifact_manifest_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(f"SELECT * FROM {MANIFEST_TABLE} WHERE work_id = ?", (work_id,))
        row = await cursor.fetchone()
    return _row_to_manifest(row) if row else None


async def patch_manifest(
    db_path: str,
    work_id: str,
    *,
    manifest_patch: dict[str, Any] | None = None,
    content_revision: str = "",
    expected_manifest_version: int | None = None,
) -> dict[str, Any]:
    manifest = await get_manifest(db_path, work_id)
    if not manifest:
        return {"status": "not_found", "reason_code": "manifest_not_found"}
    current_version = int(manifest.get("manifest_version") or 0)
    if expected_manifest_version is not None and expected_manifest_version != current_version:
        return {
            "status": "version_conflict",
            "reason_code": "manifest_version_conflict",
            "current_version": current_version,
        }
    patch = dict(manifest_patch or {})
    intent = dict(manifest.get("structured_intent") or {})
    intent.update(_jsonable_dict(patch))
    revision = " ".join(content_revision.strip().split())
    if revision:
        revisions = list(intent.get("content_revisions") or [])
        revisions.append({"text": revision, "created_at": _now_iso()})
        intent["content_revisions"] = revisions
    next_version = current_version + 1
    title = _clean_title(str(patch.get("title") or manifest.get("title") or ""))
    topic = str(patch.get("topic") or manifest.get("topic") or "").strip()
    audience = str(patch.get("audience") or manifest.get("audience") or "").strip()
    artifact_type = str(patch.get("artifact_type") or manifest.get("artifact_type") or "").strip()
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            UPDATE {MANIFEST_TABLE}
            SET manifest_version = ?,
                artifact_type = ?,
                title = ?,
                topic = ?,
                audience = ?,
                structured_intent_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE work_id = ?
            """,
            (
                next_version,
                artifact_type,
                title,
                topic,
                audience,
                json.dumps(intent, sort_keys=True),
                work_id,
            ),
        )
        await db.commit()
    return {"status": "ok", "manifest": await get_manifest(db_path, work_id), "version": next_version}


async def current_manifest_title(fallback: str = "") -> str:
    db_path = current_voice_work_db_path()
    work_id = current_voice_work_id()
    manifest = await get_manifest(db_path, work_id) if db_path and work_id else None
    title = str((manifest or {}).get("title") or "").strip()
    return title or fallback


async def record_current_render_report_for_sections(path: Path, sections: list[tuple[str, list[str]]]) -> dict[str, Any]:
    db_path = current_voice_work_db_path()
    work_id = current_voice_work_id()
    if not db_path or not work_id:
        return {"status": "skipped", "reason_code": "no_voice_manifest"}
    manifest = await get_manifest(db_path, work_id)
    if not manifest:
        return {"status": "failed", "reason_code": "manifest_not_found"}
    headings = [str(title) for title, _items in sections]
    intent = dict(manifest.get("structured_intent") or {})
    duration_days = _int_or_none(intent.get("duration_days"))
    fields_rendered: dict[str, Any] = {}
    status = "ok"
    reason = ""
    if duration_days is not None:
        actual_days = _day_section_count(headings)
        fields_rendered["duration_days"] = {"expected": duration_days, "sections_created": actual_days}
        if actual_days < duration_days:
            status = "failed"
            reason = "render_report_mismatch"
    report = await record_render_report(
        db_path,
        work_id=work_id,
        manifest_version_used=int(manifest.get("manifest_version") or 0),
        artifact_path=str(path),
        fields_rendered=fields_rendered,
        sections_created=headings,
        status=status,
        reason_code=reason,
    )
    return report


async def apply_current_manifest_count_sections(
    sections: list[tuple[str, list[str]]],
) -> list[tuple[str, list[str]]]:
    db_path = current_voice_work_db_path()
    work_id = current_voice_work_id()
    manifest = await get_manifest(db_path, work_id) if db_path and work_id else None
    intent = dict((manifest or {}).get("structured_intent") or {})
    duration_days = _int_or_none(intent.get("duration_days"))
    if duration_days is None:
        return sections
    existing_numbers = _day_numbers([str(title) for title, _items in sections])
    next_sections = list(sections)
    for day in range(1, duration_days + 1):
        if day not in existing_numbers:
            next_sections.append(
                (
                    f"Day {day} Plan",
                    [
                        (
                            "This day was added from the structured itinerary duration. "
                            "Review and fill in the day details before treating the document as final."
                        )
                    ],
                )
            )
    return next_sections


async def record_render_report(
    db_path: str,
    *,
    work_id: str,
    manifest_version_used: int,
    artifact_path: str,
    fields_rendered: dict[str, Any] | None = None,
    sections_created: list[str] | None = None,
    status: str = "ok",
    reason_code: str = "",
) -> dict[str, Any]:
    await init_artifact_manifest_db(db_path)
    digest = _sha256(artifact_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            f"""
            INSERT INTO {RENDER_REPORT_TABLE}
                (work_id, manifest_version_used, artifact_path, sha256, fields_rendered_json,
                 sections_created_json, status, reason_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                work_id,
                manifest_version_used,
                artifact_path,
                digest,
                json.dumps(fields_rendered or {}, sort_keys=True),
                json.dumps(sections_created or []),
                status,
                reason_code,
            ),
        )
        report_id = cursor.lastrowid
        await db.commit()
    return {
        "id": report_id,
        "work_id": work_id,
        "manifest_version_used": manifest_version_used,
        "artifact_path": artifact_path,
        "sha256": digest,
        "fields_rendered": fields_rendered or {},
        "sections_created": sections_created or [],
        "status": status,
        "reason_code": reason_code,
    }


def _row_to_manifest(row) -> dict[str, Any]:
    return {
        "work_id": row["work_id"],
        "manifest_version": int(row["manifest_version"] or 0),
        "artifact_type": row["artifact_type"] or "",
        "title": row["title"] or "",
        "topic": row["topic"] or "",
        "audience": row["audience"] or "",
        "request": row["request"] or "",
        "structured_intent": _loads(row["structured_intent_json"], {}),
        "source_turn_ids": _loads(row["source_turn_ids_json"], []),
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
    }


def _structured_intent(args: dict[str, Any], *, request: str, kind: str) -> dict[str, Any]:
    intent = {"request": request.strip(), "kind": kind}
    for key in ("artifact_type", "artifact_topic", "topic", "title", "audience", "duration_days"):
        if args.get(key) not in (None, ""):
            intent[key] = args[key]
    return _jsonable_dict(intent)


def _jsonable_dict(values: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in values.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            clean[str(key)] = value
        elif isinstance(value, list):
            clean[str(key)] = [_jsonable_value(item) for item in value if _jsonable_value(item) is not None]
        elif isinstance(value, dict):
            clean[str(key)] = _jsonable_dict(value)
    return clean


def _jsonable_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return _jsonable_dict(value)
    if isinstance(value, list):
        return [_jsonable_value(item) for item in value if _jsonable_value(item) is not None]
    return None


def _clean_title(title: str) -> str:
    clean = re.sub(r"[\r\n\t/\\\\:]+", " ", str(title or "")).strip()
    clean = re.sub(r"\s{2,}", " ", clean)
    return clean[:90].rstrip()


def _loads(raw: str, fallback):
    try:
        return json.loads(raw or "")
    except (TypeError, ValueError):
        return fallback


def _sha256(path: str) -> str:
    target = Path(path)
    if not target.exists() or not target.is_file():
        return ""
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _day_section_count(headings: list[str]) -> int:
    return sum(1 for heading in headings if re.match(r"(?i)^\s*day\s+\d+\b", heading))


def _day_numbers(headings: list[str]) -> set[int]:
    numbers: set[int] = set()
    for heading in headings:
        match = re.match(r"(?i)^\s*day\s+(\d+)\b", heading)
        if match:
            numbers.add(int(match.group(1)))
    return numbers


def _int_or_none(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"
