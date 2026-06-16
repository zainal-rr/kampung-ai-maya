from __future__ import annotations

import uuid
import re

import aiosqlite


VOICE_WORK_TABLE = "voice_work_requests"
ACTIVE_PHASES = {"queued", "preflight", "drafting", "building", "qa", "opening"}
TERMINAL_PHASES = {"done", "failed", "cancelled"}


async def init_voice_work_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {VOICE_WORK_TABLE} (
                id TEXT PRIMARY KEY,
                request TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'work',
                status TEXT NOT NULL DEFAULT 'queued',
                source TEXT DEFAULT 'imac_voice',
                voice_session_id TEXT DEFAULT '',
                short_ack TEXT DEFAULT '',
                result TEXT DEFAULT '',
                result_summary TEXT DEFAULT '',
                artifact_path TEXT DEFAULT '',
                phase TEXT NOT NULL DEFAULT 'queued',
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                cancel_reason TEXT DEFAULT '',
                revision_count INTEGER NOT NULL DEFAULT 0,
                phase_detail TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await _ensure_voice_work_columns(db)
        await db.commit()


async def _ensure_voice_work_columns(db: aiosqlite.Connection) -> None:
    cursor = await db.execute(f"PRAGMA table_info({VOICE_WORK_TABLE})")
    columns = {str(row[1]) for row in await cursor.fetchall()}
    migrations = {
        "short_ack": "ALTER TABLE voice_work_requests ADD COLUMN short_ack TEXT DEFAULT ''",
        "result_summary": "ALTER TABLE voice_work_requests ADD COLUMN result_summary TEXT DEFAULT ''",
        "artifact_path": "ALTER TABLE voice_work_requests ADD COLUMN artifact_path TEXT DEFAULT ''",
        "phase": "ALTER TABLE voice_work_requests ADD COLUMN phase TEXT NOT NULL DEFAULT 'queued'",
        "cancel_requested": "ALTER TABLE voice_work_requests ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0",
        "cancel_reason": "ALTER TABLE voice_work_requests ADD COLUMN cancel_reason TEXT DEFAULT ''",
        "revision_count": "ALTER TABLE voice_work_requests ADD COLUMN revision_count INTEGER NOT NULL DEFAULT 0",
        "phase_detail": "ALTER TABLE voice_work_requests ADD COLUMN phase_detail TEXT DEFAULT ''",
    }
    for column, sql in migrations.items():
        if column not in columns:
            await db.execute(sql)


async def create_voice_work(
    db_path: str,
    request: str,
    *,
    kind: str = "work",
    source: str = "imac_voice",
    voice_session_id: str = "",
    short_ack: str = "",
) -> str | None:
    cleaned = " ".join(request.strip().split())
    if not cleaned:
        return None
    await init_voice_work_db(db_path)
    work_id = f"vw_{uuid.uuid4().hex[:12]}"
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            INSERT INTO {VOICE_WORK_TABLE} (id, request, kind, status, source, voice_session_id, short_ack, phase)
            VALUES (?, ?, ?, 'queued', ?, ?, ?, 'queued')
            """,
            (work_id, cleaned, kind, source, voice_session_id, short_ack.strip()),
        )
        await db.commit()
    return work_id


async def mark_voice_work_running(db_path: str, work_id: str | None) -> None:
    if not work_id:
        return
    await init_voice_work_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            UPDATE {VOICE_WORK_TABLE}
            SET status = 'running',
                phase = CASE WHEN phase IN ('done', 'failed', 'cancelled') THEN phase ELSE 'drafting' END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (work_id,),
        )
        await db.commit()


async def complete_voice_work(
    db_path: str,
    work_id: str | None,
    *,
    result: str = "",
    status: str = "completed",
    artifact_path: str = "",
) -> None:
    if not work_id:
        return
    await init_voice_work_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        extracted_path = artifact_path or _extract_artifact_path(result)
        phase = _terminal_phase_for_status(status)
        await db.execute(
            f"""
            UPDATE {VOICE_WORK_TABLE}
            SET status = ?,
                result = ?,
                result_summary = ?,
                artifact_path = ?,
                phase = ?,
                phase_detail = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                result[:3000],
                _one_line(result, limit=500),
                extracted_path[:1000],
                phase,
                _one_line(result, limit=500) if phase == "failed" else "",
                work_id,
            ),
        )
        await db.commit()


async def get_voice_work(db_path: str, work_id: str | None) -> dict | None:
    if not work_id:
        return None
    await init_voice_work_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(f"SELECT * FROM {VOICE_WORK_TABLE} WHERE id = ?", (work_id,))
        row = await cursor.fetchone()
    return dict(row) if row else None


async def set_voice_work_phase(db_path: str, work_id: str | None, phase: str, detail: str = "") -> bool:
    if not work_id:
        return False
    if phase not in ACTIVE_PHASES | TERMINAL_PHASES:
        raise ValueError(f"unknown voice work phase: {phase}")
    await init_voice_work_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"SELECT phase, cancel_requested FROM {VOICE_WORK_TABLE} WHERE id = ?",
            (work_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return False
        if int(row["cancel_requested"] or 0) and phase == "opening":
            await db.execute(
                f"""
                UPDATE {VOICE_WORK_TABLE}
                SET status = 'cancelled',
                    phase = 'cancelled',
                    phase_detail = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (detail or "cancelled_before_opening", work_id),
            )
            await db.commit()
            return False
        status = _status_for_phase(phase)
        await db.execute(
            f"""
            UPDATE {VOICE_WORK_TABLE}
            SET phase = ?,
                status = ?,
                phase_detail = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (phase, status, detail[:1000], work_id),
        )
        await db.commit()
    return True


async def request_voice_work_cancel(db_path: str, work_id: str | None, reason: str = "") -> dict:
    row = await get_voice_work(db_path, work_id)
    if not row:
        return {"status": "not_found"}
    phase = str(row.get("phase") or "")
    if phase in TERMINAL_PHASES:
        return {"status": "already_completed", "phase": phase}
    await init_voice_work_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            UPDATE {VOICE_WORK_TABLE}
            SET cancel_requested = 1,
                cancel_reason = ?,
                phase_detail = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (reason[:1000], reason[:1000], work_id),
        )
        await db.commit()
    return {"status": "cancel_requested", "phase": phase}


async def voice_work_cancel_requested(db_path: str, work_id: str | None) -> bool:
    row = await get_voice_work(db_path, work_id)
    return bool(row and int(row.get("cancel_requested") or 0))


async def increment_voice_work_revision(db_path: str, work_id: str | None) -> int:
    if not work_id:
        return 0
    await init_voice_work_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            UPDATE {VOICE_WORK_TABLE}
            SET revision_count = revision_count + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (work_id,),
        )
        cursor = await db.execute(
            f"SELECT revision_count FROM {VOICE_WORK_TABLE} WHERE id = ?",
            (work_id,),
        )
        row = await cursor.fetchone()
        await db.commit()
    return int(row[0] or 0) if row else 0


async def resolve_latest_active_voice_work(
    db_path: str,
    *,
    work_id: str | None = None,
    voice_session_id: str = "",
) -> dict:
    if work_id:
        row = await get_voice_work(db_path, work_id)
        if not row:
            return {"status": "not_found"}
        phase = str(row.get("phase") or "")
        if phase in TERMINAL_PHASES:
            return {"status": "already_completed", "work": row}
        return {"status": "ok", "work": row}
    await init_voice_work_db(db_path)
    active = tuple(sorted(ACTIVE_PHASES))
    placeholders = ",".join("?" for _ in active)
    params: list[str] = list(active)
    session_clause = ""
    if voice_session_id:
        session_clause = "AND voice_session_id = ?"
        params.append(voice_session_id)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT *
            FROM {VOICE_WORK_TABLE}
            WHERE phase IN ({placeholders})
              {session_clause}
            ORDER BY datetime(created_at) DESC, id DESC
            LIMIT 2
            """,
            tuple(params),
        )
        rows = await cursor.fetchall()
    if not rows:
        return {"status": "not_found"}
    if len(rows) > 1:
        return {"status": "needs_clarification", "works": [dict(row) for row in rows]}
    return {"status": "ok", "work": dict(rows[0])}


async def voice_work_status_text(db_path: str, *, limit: int = 6) -> str:
    await init_voice_work_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT id, request, kind, status, phase, cancel_requested, revision_count, phase_detail,
                   short_ack, result, result_summary, artifact_path, created_at, updated_at
            FROM {VOICE_WORK_TABLE}
            ORDER BY
                CASE phase
                    WHEN 'drafting' THEN 0
                    WHEN 'building' THEN 1
                    WHEN 'qa' THEN 2
                    WHEN 'opening' THEN 3
                    WHEN 'queued' THEN 1
                    WHEN 'failed' THEN 4
                    WHEN 'cancelled' THEN 5
                    WHEN 'done' THEN 6
                    ELSE 4
                END,
                datetime(updated_at) DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    if not rows:
        return "No active Maya work from this voice session yet."
    lines = ["Maya voice work:"]
    for index, row in enumerate(rows, start=1):
        request = str(row["request"])
        status = str(row["status"])
        phase = str(row["phase"] or status)
        kind = str(row["kind"])
        result = str(row["result_summary"] or row["result"] or "").strip()
        short_ack = str(row["short_ack"] or "").strip()
        artifact_path = str(row["artifact_path"] or "").strip()
        revision_count = int(row["revision_count"] or 0)
        cancel_requested = bool(int(row["cancel_requested"] or 0))
        suffix = ""
        if phase in {"done", "failed", "cancelled"} and result:
            suffix = f" Result: {_one_line(result)}"
        if artifact_path:
            suffix += f" File: {artifact_path}"
        if revision_count:
            suffix += f" Revisions: {revision_count}"
        if cancel_requested and phase not in TERMINAL_PHASES:
            suffix += " Cancel requested."
        ack = f" Acknowledged: {short_ack}" if short_ack and phase in ACTIVE_PHASES else ""
        lines.append(f"{index}) {phase} {kind}: {request}.{ack}{suffix}")
    try:
        from maya_documents.artifact_steering import latest_steer_status_text

        steering = await latest_steer_status_text(db_path)
        if steering:
            lines.append("")
            lines.append(steering)
    except Exception:
        pass
    return "\n".join(lines)


def _one_line(text: str, *, limit: int = 240) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "..."


def _extract_artifact_path(text: str) -> str:
    match = re.search(r"(/Users/[^\n\r\t]+?\.(?:docx|xlsx|pptx|md|html|png|svg|pdf))", text)
    return match.group(1).strip(" .)") if match else ""


def _terminal_phase_for_status(status: str) -> str:
    if status == "completed":
        return "done"
    if status == "cancelled":
        return "cancelled"
    return "failed"


def _status_for_phase(phase: str) -> str:
    if phase == "done":
        return "completed"
    if phase == "cancelled":
        return "cancelled"
    if phase == "failed":
        return "failed"
    if phase in ACTIVE_PHASES:
        return "running" if phase != "queued" else "queued"
    return "running"
