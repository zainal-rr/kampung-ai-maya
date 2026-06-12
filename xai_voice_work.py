from __future__ import annotations

import uuid
import re

import aiosqlite


VOICE_WORK_TABLE = "voice_work_requests"


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
            INSERT INTO {VOICE_WORK_TABLE} (id, request, kind, status, source, voice_session_id, short_ack)
            VALUES (?, ?, ?, 'queued', ?, ?, ?)
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
            SET status = 'running', updated_at = CURRENT_TIMESTAMP
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
        await db.execute(
            f"""
            UPDATE {VOICE_WORK_TABLE}
            SET status = ?,
                result = ?,
                result_summary = ?,
                artifact_path = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, result[:3000], _one_line(result, limit=500), extracted_path[:1000], work_id),
        )
        await db.commit()


async def voice_work_status_text(db_path: str, *, limit: int = 6) -> str:
    await init_voice_work_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT id, request, kind, status, short_ack, result, result_summary, artifact_path, created_at, updated_at
            FROM {VOICE_WORK_TABLE}
            ORDER BY
                CASE status
                    WHEN 'running' THEN 0
                    WHEN 'queued' THEN 1
                    WHEN 'failed' THEN 2
                    WHEN 'completed' THEN 3
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
        kind = str(row["kind"])
        result = str(row["result_summary"] or row["result"] or "").strip()
        short_ack = str(row["short_ack"] or "").strip()
        artifact_path = str(row["artifact_path"] or "").strip()
        suffix = ""
        if status in {"completed", "failed"} and result:
            suffix = f" Result: {_one_line(result)}"
        if artifact_path:
            suffix += f" File: {artifact_path}"
        ack = f" Acknowledged: {short_ack}" if short_ack and status in {"queued", "running"} else ""
        lines.append(f"{index}) {status} {kind}: {request}.{ack}{suffix}")
    try:
        from artifact_steering import latest_steer_status_text

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
