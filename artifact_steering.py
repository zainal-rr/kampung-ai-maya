from __future__ import annotations

import re
import uuid
from pathlib import Path

import aiosqlite

from artifact_file_state import artifact_changed_since_recorded
from artifact_sessions import active_artifact_session


STEER_TABLE = "artifact_steer_events"


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
    channel: str = "imac",
) -> str:
    steer_texts = [item.strip() for item in steer_texts if item.strip()]
    if not steer_texts:
        return ""
    instruction = _combined_instruction(steer_texts)
    session = await active_artifact_session(db_path, channel)
    if not session:
        await _mark_many(db_path, event_ids, status="failed", action_taken="no_active_artifact")
        return "I captured your update, but I could not find the created artifact to revise."
    path = Path(session.path)
    copy_needed = await _copy_needed(db_path, path, session.artifact_type, instruction)
    edit_request = _edit_request(instruction, copy_needed=copy_needed)
    try:
        reply = await assistant.handle_text(edit_request, channel=channel, speak_reply=False)
    except Exception as exc:
        await _mark_many(db_path, event_ids, status="failed", action_taken=f"edit_failed:{exc}")
        return f"I captured your update, but I could not apply it yet: {exc}"
    action = "created_versioned_copy" if copy_needed else "edited_in_place"
    artifact_path = _extract_artifact_path(str(reply)) or str(path)
    await _mark_many(db_path, event_ids, status="applied", action_taken=action, artifact_path=artifact_path)
    return _steer_result_text(instruction, str(reply), copy_needed=copy_needed)


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


async def _mark_many(db_path: str, event_ids: list[str], *, status: str, action_taken: str, artifact_path: str = "") -> None:
    for event_id in event_ids:
        await update_artifact_steer_event(db_path, event_id, status=status, action_taken=action_taken, artifact_path=artifact_path)


async def _copy_needed(db_path: str, path: Path, artifact_type: str, instruction: str) -> bool:
    if artifact_type == "pptx":
        return True
    if await artifact_changed_since_recorded(db_path, path):
        return True
    if artifact_type == "xlsx" and not _simple_excel_steer(instruction):
        return True
    return False


def _simple_excel_steer(instruction: str) -> bool:
    lowered = instruction.lower()
    return any(marker in lowered for marker in ("note column", "notes column", "people", "pax", "traveler", "traveller", "guest"))


def _edit_request(instruction: str, *, copy_needed: bool) -> str:
    cleaned = " ".join(instruction.split()).strip(" .")
    if copy_needed:
        return f"make a new version of that with {cleaned}"
    return f"update the latest document to {cleaned}"


def _combined_instruction(items: list[str]) -> str:
    unique = []
    for item in items:
        cleaned = " ".join(item.split()).strip(" .")
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return "; ".join(unique)


def _steer_result_text(instruction: str, reply: str, *, copy_needed: bool) -> str:
    mode = "I made a new version so I would not overwrite your edits." if copy_needed else "I applied it to the current artifact."
    return f"Steer update applied: {instruction}. {mode}\n{reply}"


def _extract_artifact_path(text: str) -> str:
    match = re.search(r"(/Users/[^\n\r\t]+?\.(?:docx|xlsx|pptx|md|html|png|svg|pdf))", text)
    return match.group(1).strip(" .)") if match else ""
