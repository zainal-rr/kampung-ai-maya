from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import aiosqlite

from harness_store import init_harness_db, record_event


EVENT_TYPES = {
    "user_message",
    "assistant_message",
    "route_decision",
    "tool_requested",
    "tool_started",
    "tool_completed",
    "approval_requested",
    "approval_resolved",
    "artifact_created",
    "memory_written",
    "skill_selected",
    "workflow_paused",
    "workflow_resumed",
    "thread_started",
}


class MayaEventStore:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def append(
        self,
        event_type: str,
        *,
        thread_id: str,
        run_id: str = "",
        actor: str = "maya",
        summary: str = "",
        payload: Mapping[str, Any] | None = None,
    ) -> int:
        await init_maya_event_db(self.db_path)
        clean_type = event_type if event_type in EVENT_TYPES else "tool_completed"
        payload_json = json.dumps(dict(payload or {}), sort_keys=True, default=str)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO maya_events (
                    thread_id, run_id, event_type, actor, summary, payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (thread_id, run_id, clean_type, actor, summary[:1000], payload_json[:4000]),
            )
            await db.commit()
            event_id = int(cursor.lastrowid or 0)
        if run_id:
            await record_event(self.db_path, run_id, clean_type, summary or payload_json)
        return event_id

    async def list(
        self,
        *,
        thread_id: str | None = None,
        run_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        await init_maya_event_db(self.db_path)
        where, params = _where(thread_id, run_id, limit)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"""
                SELECT id, thread_id, run_id, event_type, actor,
                       summary, payload_json, created_at
                FROM maya_events
                {where}
                ORDER BY id DESC
                LIMIT ?
                """,
                params,
            )
            rows = await cursor.fetchall()
        return [_decode_row(row) for row in reversed(rows)]


async def init_maya_event_db(db_path: str) -> None:
    await init_harness_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS maya_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id TEXT NOT NULL,
                run_id TEXT DEFAULT '',
                event_type TEXT NOT NULL,
                actor TEXT DEFAULT 'maya',
                summary TEXT DEFAULT '',
                payload_json TEXT DEFAULT '{}',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute("CREATE INDEX IF NOT EXISTS idx_maya_events_thread ON maya_events(thread_id, id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_maya_events_run ON maya_events(run_id, id)")
        await db.commit()


def _where(thread_id: str | None, run_id: str | None, limit: int) -> tuple[str, tuple[Any, ...]]:
    if thread_id and run_id:
        return "WHERE thread_id = ? AND run_id = ?", (thread_id, run_id, limit)
    if thread_id:
        return "WHERE thread_id = ?", (thread_id, limit)
    if run_id:
        return "WHERE run_id = ?", (run_id, limit)
    return "", (limit,)


def _decode_row(row: aiosqlite.Row) -> dict[str, Any]:
    data = dict(row)
    try:
        data["payload"] = json.loads(str(data.pop("payload_json") or "{}"))
    except json.JSONDecodeError:
        data["payload"] = {}
    return data
