from __future__ import annotations

import asyncio
import os

import aiosqlite

from active_context_parsers import _safe_path
from maya_voice.active_context_inspector import ActiveContextInspector
from xai_voice_work import (
    VOICE_WORK_TABLE,
    get_voice_work,
    init_voice_work_db,
    resolve_latest_active_voice_work,
)


async def resolve_voice_work_for_revision(
    db_path: str,
    *,
    work_id: str | None = None,
    voice_session_id: str = "",
) -> dict:
    """Resolve a revision target without silently crossing voice sessions."""

    if work_id:
        row = await get_voice_work(db_path, work_id)
        if not row:
            return {"status": "not_found"}
        row_session = str(row.get("voice_session_id") or "")
        if voice_session_id and row_session and row_session != voice_session_id:
            return {"status": "needs_confirmation", "work": row}
        return {"status": "ok", "work": row}

    active = await resolve_latest_active_voice_work(
        db_path,
        work_id=None,
        voice_session_id=voice_session_id,
    )
    if active.get("status") in {"ok", "needs_clarification"}:
        return active

    active_office_artifact = await _active_office_artifact_work(db_path)
    if active_office_artifact:
        return {"status": "ok", "work": active_office_artifact}

    same_session = await _latest_completed_artifact_work(
        db_path,
        voice_session_id=voice_session_id,
        same_session=True,
    )
    if same_session:
        return {"status": "ok", "work": same_session}

    cross_session = await _latest_completed_artifact_work(
        db_path,
        voice_session_id=voice_session_id,
        same_session=False,
    )
    if cross_session:
        return {"status": "needs_confirmation", "work": cross_session}

    return {"status": "not_found"}


async def _active_office_artifact_work(db_path: str) -> dict | None:
    """Prefer the foreground Office artifact over stale completed history."""

    try:
        timeout = float(os.getenv("MAYA_ACTIVE_OFFICE_RESOLVE_SECONDS", "2.0"))
    except ValueError:
        timeout = 2.0
    try:
        path = await asyncio.wait_for(_active_office_path(db_path), timeout=max(0.2, timeout))
    except (asyncio.TimeoutError, Exception):
        return None
    if not path:
        return None
    return await _completed_artifact_work_for_path(db_path, path)


async def _active_office_path(db_path: str) -> str:
    try:
        context = await ActiveContextInspector(db_path).inspect(
            "current active Office artifact for revision",
            allow_screen_fallback=False,
        )
    except Exception:
        return ""
    app = str(context.app or "").lower()
    if not any(name in app for name in ("word", "excel", "powerpoint")):
        return ""
    path = _safe_path(str(context.active_file or ""))
    if not path:
        return ""
    return str(path)


async def _completed_artifact_work_for_path(db_path: str, path: str) -> dict | None:
    await init_voice_work_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT *
            FROM {VOICE_WORK_TABLE}
            WHERE phase = 'done'
              AND artifact_path = ?
            ORDER BY datetime(updated_at) DESC, datetime(created_at) DESC, id DESC
            LIMIT 1
            """,
            (path,),
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


async def _latest_completed_artifact_work(
    db_path: str,
    *,
    voice_session_id: str = "",
    same_session: bool,
) -> dict | None:
    await init_voice_work_db(db_path)
    params: list[str] = []
    session_clause = ""
    if voice_session_id:
        session_clause = "AND voice_session_id = ?" if same_session else "AND voice_session_id != ?"
        params.append(voice_session_id)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT *
            FROM {VOICE_WORK_TABLE}
            WHERE phase = 'done'
              AND COALESCE(artifact_path, '') != ''
              {session_clause}
            ORDER BY datetime(updated_at) DESC, datetime(created_at) DESC, id DESC
            LIMIT 1
            """,
            tuple(params),
        )
        row = await cursor.fetchone()
    return dict(row) if row else None
