from __future__ import annotations

import json
import uuid

import aiosqlite

async def init_harness_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS harness_runs (
                run_id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                channel TEXT DEFAULT 'imac',
                workflow_type TEXT DEFAULT 'general',
                goal TEXT DEFAULT '',
                state_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'running',
                current_step INTEGER DEFAULT 0,
                last_error TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS harness_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                event TEXT NOT NULL,
                details TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS harness_artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                kind TEXT DEFAULT '',
                path TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS harness_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


def new_run_id() -> str:
    return f"hrn_{uuid.uuid4().hex[:12]}"


async def upsert_run(db_path: str, state: dict, status: str = "running") -> None:
    await init_harness_db(db_path)
    run_id = str(state["run_id"])
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO harness_runs (
                run_id, thread_id, channel, workflow_type, goal,
                state_json, status, current_step, last_error, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(run_id) DO UPDATE SET
                thread_id = excluded.thread_id,
                channel = excluded.channel,
                workflow_type = excluded.workflow_type,
                goal = excluded.goal,
                state_json = excluded.state_json,
                status = excluded.status,
                current_step = excluded.current_step,
                last_error = excluded.last_error,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                run_id,
                str(state.get("thread_id") or "maya:shared"),
                str(state.get("channel") or "imac"),
                str(state.get("workflow_type") or "general"),
                str(state.get("goal") or ""),
                json.dumps(state),
                status,
                int(state.get("current_step") or 0),
                str(state.get("last_error") or ""),
            ),
        )
        await db.commit()


async def record_event(db_path: str, run_id: str, event: str, details: str = "") -> None:
    await init_harness_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT 1 FROM harness_events
            WHERE run_id = ? AND event = ? AND details = ?
            ORDER BY id DESC LIMIT 1
            """,
            (run_id, event, details[:1000]),
        )
        if await cursor.fetchone():
            return
        await db.execute(
            "INSERT INTO harness_events (run_id, event, details) VALUES (?, ?, ?)",
            (run_id, event, details[:1000]),
        )
        await db.commit()


async def record_artifact(db_path: str, run_id: str, kind: str, path: str, summary: str = "") -> None:
    await init_harness_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT 1 FROM harness_artifacts WHERE run_id = ? AND path = ? LIMIT 1",
            (run_id, path),
        )
        if await cursor.fetchone():
            return
        await db.execute(
            "INSERT INTO harness_artifacts (run_id, kind, path, summary) VALUES (?, ?, ?, ?)",
            (run_id, kind, path, summary[:500]),
        )
        await db.commit()


async def create_approval(db_path: str, run_id: str, action: str, details: str) -> None:
    await init_harness_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT 1 FROM harness_approvals
            WHERE run_id = ? AND action = ? AND status = 'pending'
            LIMIT 1
            """,
            (run_id, action),
        )
        if await cursor.fetchone():
            return
        await db.execute(
            "INSERT INTO harness_approvals (run_id, action, details) VALUES (?, ?, ?)",
            (run_id, action, details[:1000]),
        )
        await db.commit()


async def resolve_approval(db_path: str, run_id: str, status: str) -> None:
    await init_harness_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE harness_approvals
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE run_id = ? AND status = 'pending'
            """,
            (status, run_id),
        )
        await db.commit()


async def get_active_run(db_path: str, channel: str | None = None) -> dict | None:
    runs = await list_active_runs(db_path, channel, limit=1)
    return runs[0] if runs else None


async def list_active_runs(db_path: str, channel: str | None = None, limit: int = 10) -> list[dict]:
    await init_harness_db(db_path)
    where = "status IN ('running', 'paused')"
    params: tuple[str | int, ...]
    if channel:
        where += " AND channel = ?"
        params = (channel, limit)
    else:
        params = (limit,)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT *
            FROM harness_runs
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            params,
        )
        rows = await cursor.fetchall()
    return [_row_to_run(row) for row in rows]


async def get_run(db_path: str, run_id: str) -> dict | None:
    await init_harness_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM harness_runs WHERE run_id = ?", (run_id,))
        row = await cursor.fetchone()
    return _row_to_run(row) if row else None


async def finish_run(db_path: str, run_id: str, status: str = "completed") -> None:
    await init_harness_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE harness_runs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE run_id = ?",
            (status, run_id),
        )
        await db.commit()


async def latest_events(db_path: str, run_id: str, limit: int = 8) -> list[dict[str, str]]:
    await init_harness_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT event, details, created_at
            FROM harness_events
            WHERE run_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (run_id, limit),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in reversed(rows)]


def _row_to_run(row) -> dict:
    data = dict(row)
    data["state"] = json.loads(str(data.pop("state_json") or "{}"))
    return data
