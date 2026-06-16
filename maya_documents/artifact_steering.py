from __future__ import annotations

import re
import uuid
from pathlib import Path

import aiosqlite

from maya_documents.artifact_file_state import artifact_changed_since_recorded
from maya_documents.artifact_file_state import record_artifact_fingerprint
from maya_documents.artifact_sessions import active_artifact_session, record_artifact_session
from maya_voice.revision_delivery import reopen_revised_artifact, verify_revision_postcondition, word_open_with_unsaved_changes
from maya_core.storage import get_preference
from maya_core.storage import upsert_preference


STEER_TABLE = "artifact_steer_events"
LAST_DOC_KEY = "maya_last_document_path"


async def init_artifact_steering_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {STEER_TABLE} (
                id TEXT PRIMARY KEY,
                work_id TEXT DEFAULT '',
                voice_session_id TEXT DEFAULT '',
                artifact_type TEXT DEFAULT '',
                original_request TEXT DEFAULT '',
                steer_text TEXT NOT NULL,
                timing TEXT NOT NULL,
                action_taken TEXT DEFAULT '',
                artifact_path TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'captured',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(f"CREATE INDEX IF NOT EXISTS idx_artifact_steer_work ON {STEER_TABLE}(work_id, created_at)")
        await db.commit()


async def create_artifact_steer_event(
    db_path: str,
    *,
    work_id: str = "",
    voice_session_id: str = "",
    artifact_type: str = "",
    original_request: str = "",
    steer_text: str,
    timing: str,
) -> str:
    await init_artifact_steering_db(db_path)
    event_id = f"steer_{uuid.uuid4().hex[:12]}"
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            INSERT INTO {STEER_TABLE}
                (id, work_id, voice_session_id, artifact_type, original_request, steer_text, timing, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'captured')
            """,
            (
                event_id,
                work_id,
                voice_session_id,
                artifact_type,
                original_request,
                steer_text,
                timing,
            ),
        )
        await db.commit()
    return event_id


async def update_artifact_steer_event(
    db_path: str,
    event_id: str,
    *,
    status: str,
    action_taken: str = "",
    artifact_path: str = "",
) -> None:
    if not event_id:
        return
    await init_artifact_steering_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            UPDATE {STEER_TABLE}
            SET status = ?, action_taken = ?, artifact_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, action_taken, artifact_path, event_id),
        )
        await db.commit()


async def apply_late_artifact_steers(
    db_path: str,
    *,
    assistant,
    work_id: str,
    voice_session_id: str,
    original_request: str,
    steer_texts: list[str],
    event_ids: list[str],
    patch_type: str = "",
    postcondition: dict | None = None,
    channel: str = "imac",
) -> str:
    steer_texts = [item.strip() for item in steer_texts if item.strip()]
    if not steer_texts:
        return ""
    instruction = _combined_instruction(steer_texts)
    target_path = await _voice_work_artifact_path(db_path, work_id)
    if not target_path:
        target_path = await _event_voice_work_artifact_path(db_path, event_ids)
    if not target_path:
        requested_type = await _event_artifact_type(db_path, event_ids)
        preferred_path = str(await get_preference(db_path, LAST_DOC_KEY) or "").strip()
        if _path_matches_artifact_type(preferred_path, requested_type):
            target_path = preferred_path
    session = await active_artifact_session(db_path, channel, target_path or None)
    if target_path and not session:
        path = Path(target_path)
        if path.exists():
            artifact_type = _artifact_type_from_path(path)
            session = await record_artifact_session(db_path, channel, artifact_type, path, original_request or path.stem)
            await record_artifact_fingerprint(db_path, path)
    if not session:
        await _mark_many(db_path, event_ids, status="failed", action_taken="no_active_artifact")
        return _revision_result_text(
            "missing_artifact",
            "I captured your update, but I could not find the created artifact to revise.",
        )
    path = Path(session.path)
    if not path.exists():
        await _mark_many(db_path, event_ids, status="failed", action_taken="missing_artifact")
        return _revision_result_text(
            "missing_artifact",
            "I captured your update, but the created artifact is no longer on disk.",
        )
    await upsert_preference(db_path, LAST_DOC_KEY, str(path), source="artifact_steering")
    copy_reason = await _copy_reason(db_path, path, session.artifact_type, patch_type, assistant=assistant)
    copy_needed = bool(copy_reason)
    edit_request = _edit_request(instruction, copy_needed=copy_needed)
    try:
        reply = await assistant.handle_text(edit_request, channel=channel, speak_reply=False)
    except Exception as exc:
        await _mark_many(db_path, event_ids, status="failed", action_taken=f"edit_failed:{exc}")
        return _revision_result_text(
            "hard_blocked",
            f"I captured your update, but I could not apply it yet: {exc}",
        )
    action = copy_reason or "edited_in_place"
    artifact_path = _extract_artifact_path(str(reply)) or str(path)
    proof = await verify_revision_postcondition(
        db_path,
        work_id=work_id,
        artifact_path=artifact_path,
        artifact_type=session.artifact_type,
        postcondition=postcondition,
    )
    if proof.get("status") == "failed":
        detail = str(proof.get("detail") or "The saved file did not contain the requested revision proof.")
        await _mark_many(db_path, event_ids, status="failed", action_taken="revision_not_applied", artifact_path=artifact_path)
        return _revision_result_text("revision_not_applied", detail)
    await record_artifact_fingerprint(db_path, Path(artifact_path))
    open_note = await reopen_revised_artifact(assistant, Path(artifact_path), session.artifact_type, channel)
    await _mark_many(db_path, event_ids, status="applied", action_taken=action, artifact_path=artifact_path)
    return _steer_result_text(
        instruction,
        str(reply),
        copy_reason=copy_reason,
        proof_note=str(proof.get("note") or ""),
        open_note=open_note,
    )


async def latest_steer_status_text(db_path: str, *, limit: int = 4) -> str:
    await init_artifact_steering_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT steer_text, timing, status, action_taken, artifact_path, updated_at
            FROM {STEER_TABLE}
            ORDER BY datetime(updated_at) DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    if not rows:
        return ""
    lines = ["Recent artifact steering:"]
    for index, row in enumerate(rows, start=1):
        action = str(row["action_taken"] or "").strip()
        suffix = f" ({action})" if action else ""
        path = str(row["artifact_path"] or "").strip()
        if path:
            suffix += f" File: {path}"
        lines.append(f"{index}) {row['status']} {row['timing']}: {row['steer_text']}{suffix}")
    return "\n".join(lines)


async def pending_steer_events_for_work(db_path: str, work_id: str) -> list[dict[str, str]]:
    if not work_id:
        return []
    await init_artifact_steering_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT id, steer_text, timing
            FROM {STEER_TABLE}
            WHERE work_id = ?
              AND status = 'captured'
            ORDER BY datetime(created_at) ASC, id ASC
            """,
            (work_id,),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def _mark_many(db_path: str, event_ids: list[str], *, status: str, action_taken: str, artifact_path: str = "") -> None:
    for event_id in event_ids:
        await update_artifact_steer_event(db_path, event_id, status=status, action_taken=action_taken, artifact_path=artifact_path)


async def _copy_reason(db_path: str, path: Path, artifact_type: str, patch_type: str = "", *, assistant=None) -> str:
    if artifact_type == "pptx":
        return "created_v2"
    if artifact_type == "docx" and await word_open_with_unsaved_changes(assistant, path):
        return "manual_edit_detected"
    if await artifact_changed_since_recorded(db_path, path):
        return "manual_edit_detected"
    if artifact_type == "xlsx" and not _excel_patch_type_in_place_allowed(patch_type):
        return "unsupported_patch_type"
    return ""


def _excel_patch_type_in_place_allowed(patch_type: str) -> bool:
    return patch_type.strip().lower() in {"comment", "cell_comment", "context_note", "note"}


def _edit_request(instruction: str, *, copy_needed: bool) -> str:
    cleaned = " ".join(instruction.split()).strip(" .")
    if copy_needed:
        return f"make a new version of that document with {cleaned}"
    return f"update that document to {cleaned}"


def _combined_instruction(items: list[str]) -> str:
    unique = []
    for item in items:
        cleaned = " ".join(item.split()).strip(" .")
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return "; ".join(unique)


def _steer_result_text(
    instruction: str,
    reply: str,
    *,
    copy_reason: str = "",
    proof_note: str = "",
    open_note: str = "",
) -> str:
    code = copy_reason or "edited_in_place"
    if copy_reason == "manual_edit_detected":
        mode = "I made a new version because the file changed after Maya created it."
    elif copy_reason == "unsupported_patch_type":
        mode = "I made a new version because that patch type is not in the safe in-place allowlist."
    elif copy_reason:
        mode = "I made a new version so I would not overwrite your edits or risk a structural change."
    else:
        mode = "I applied it to the current artifact."
    extras = "\n".join(item for item in (proof_note, open_note) if item)
    suffix = f"\n{extras}" if extras else ""
    return f"revision_result_code: {code}\nSteer update applied: {instruction}. {mode}\n{reply}{suffix}"


def _revision_result_text(code: str, detail: str) -> str:
    return f"revision_result_code: {code}\n{detail}"


def _extract_artifact_path(text: str) -> str:
    match = re.search(r"(/Users/[^\n\r\t]+?\.(?:docx|xlsx|pptx|md|html|png|svg|pdf))", text)
    return match.group(1).strip(" .)") if match else ""


async def _voice_work_artifact_path(db_path: str, work_id: str) -> str:
    if not work_id:
        return ""
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT artifact_path FROM voice_work_requests WHERE id = ?",
            (work_id,),
        )
        row = await cursor.fetchone()
    return str(row[0] or "").strip() if row else ""


async def _event_voice_work_artifact_path(db_path: str, event_ids: list[str]) -> str:
    event_ids = [event_id for event_id in event_ids if event_id]
    if not event_ids:
        return ""
    await init_artifact_steering_db(db_path)
    placeholders = ",".join("?" for _ in event_ids)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            f"""
            SELECT v.artifact_path
            FROM {STEER_TABLE} s
            JOIN voice_work_requests v ON v.id = s.work_id
            WHERE s.id IN ({placeholders})
              AND COALESCE(v.artifact_path, '') != ''
            ORDER BY datetime(s.created_at) DESC, s.id DESC
            LIMIT 1
            """,
            tuple(event_ids),
        )
        row = await cursor.fetchone()
    return str(row[0] or "").strip() if row else ""


async def _event_artifact_type(db_path: str, event_ids: list[str]) -> str:
    event_ids = [event_id for event_id in event_ids if event_id]
    if not event_ids:
        return ""
    await init_artifact_steering_db(db_path)
    placeholders = ",".join("?" for _ in event_ids)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            f"""
            SELECT artifact_type
            FROM {STEER_TABLE}
            WHERE id IN ({placeholders})
              AND COALESCE(artifact_type, '') != ''
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 1
            """,
            tuple(event_ids),
        )
        row = await cursor.fetchone()
    return str(row[0] or "").strip().lower() if row else ""


def _path_matches_artifact_type(path: str, artifact_type: str) -> bool:
    if not path:
        return False
    if not artifact_type:
        return True
    suffix = Path(path).suffix.lower().lstrip(".")
    return suffix == artifact_type.lower().lstrip(".")


def _artifact_type_from_path(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return {"docx": "docx", "xlsx": "xlsx", "pptx": "pptx", "md": "md", "html": "html"}.get(suffix, suffix or "file")
