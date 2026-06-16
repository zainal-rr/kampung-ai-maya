from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import aiosqlite

from maya_core.retention_delete import delete_project_records, delete_task_records


RETENTION_DAYS = 90
WARNING_DAYS = 7
ACTIVE = "active"
DELETION_PENDING = "deletion_pending"


async def init_retention_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS project_activity (
                project_path TEXT PRIMARY KEY,
                project_name TEXT DEFAULT '',
                last_activity_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                retention_state TEXT DEFAULT 'active',
                deletion_pending_at DATETIME,
                deleted_at DATETIME,
                last_reason TEXT DEFAULT '',
                last_source TEXT DEFAULT ''
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS retention_tombstones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_type TEXT NOT NULL,
                object_key_hash TEXT NOT NULL,
                deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                reason TEXT DEFAULT ''
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS project_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_path TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT 'maya',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for statement in (
            "ALTER TABLE tasks ADD COLUMN retention_state TEXT DEFAULT 'active'",
            "ALTER TABLE tasks ADD COLUMN deletion_pending_at DATETIME",
            "ALTER TABLE tasks ADD COLUMN deleted_at DATETIME",
        ):
            try:
                await db.execute(statement)
            except aiosqlite.OperationalError:
                pass
        await db.commit()


async def touch_project_activity(
    db_path: str,
    project_path: str | Path,
    reason: str,
    source: str,
    now: datetime | str | None = None,
) -> None:
    await init_retention_db(db_path)
    path = Path(project_path).expanduser().resolve(strict=False)
    timestamp = _timestamp(now)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO project_activity (
                project_path, project_name, last_activity_at, retention_state,
                deletion_pending_at, deleted_at, last_reason, last_source
            )
            VALUES (?, ?, ?, 'active', NULL, NULL, ?, ?)
            ON CONFLICT(project_path) DO UPDATE SET
                project_name = excluded.project_name,
                last_activity_at = excluded.last_activity_at,
                retention_state = 'active',
                deletion_pending_at = NULL,
                deleted_at = NULL,
                last_reason = excluded.last_reason,
                last_source = excluded.last_source
            """,
            (str(path), path.name, timestamp, reason[:200], source[:80]),
        )
        await db.commit()


async def touch_task_activity(
    db_path: str,
    task_id: int,
    reason: str,
    source: str,
    now: datetime | str | None = None,
) -> None:
    await init_retention_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE tasks
            SET retention_state = 'active',
                deletion_pending_at = NULL,
                deleted_at = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (_timestamp(now), task_id),
        )
        await db.commit()


async def mark_retention_candidates(db_path: str, now: datetime | str | None = None) -> dict[str, int]:
    await init_retention_db(db_path)
    current = _datetime(now)
    stale_cutoff = _timestamp(current - timedelta(days=RETENTION_DAYS))
    current_ts = _timestamp(current)
    async with aiosqlite.connect(db_path) as db:
        projects = await db.execute(
            """
            UPDATE project_activity
            SET retention_state = 'deletion_pending',
                deletion_pending_at = ?,
                last_reason = '90-day inactivity warning',
                last_source = 'retention'
            WHERE retention_state = 'active'
              AND last_activity_at <= ?
            """,
            (current_ts, stale_cutoff),
        )
        tasks = await db.execute(
            """
            UPDATE tasks
            SET retention_state = 'deletion_pending',
                deletion_pending_at = ?
            WHERE COALESCE(retention_state, 'active') = 'active'
              AND COALESCE(updated_at, created_at) <= ?
              AND (due_at IS NULL OR due_at <= ?)
            """,
            (current_ts, stale_cutoff, current_ts),
        )
        await db.commit()
    return {"projects_marked": projects.rowcount, "tasks_marked": tasks.rowcount}


async def delete_expired_retention_candidates(db_path: str, now: datetime | str | None = None) -> dict[str, int]:
    await init_retention_db(db_path)
    expiry_cutoff = _timestamp(_datetime(now) - timedelta(days=WARNING_DAYS))
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        project_rows = await _fetch_all(
            db,
            """
            SELECT project_path, project_name
            FROM project_activity
            WHERE retention_state = 'deletion_pending'
              AND deletion_pending_at <= ?
            """,
            (expiry_cutoff,),
        )
        task_rows = await _fetch_all(
            db,
            """
            SELECT id, title, details
            FROM tasks
            WHERE retention_state = 'deletion_pending'
              AND deletion_pending_at <= ?
            """,
            (expiry_cutoff,),
        )
        deleted_projects = 0
        for row in project_rows:
            await delete_project_records(db, str(row["project_path"]), str(row["project_name"] or ""))
            deleted_projects += 1
        deleted_tasks = 0
        for row in task_rows:
            await delete_task_records(db, int(row["id"]), str(row["title"] or ""), str(row["details"] or ""))
            deleted_tasks += 1
        await db.commit()
    return {"projects_deleted": deleted_projects, "tasks_deleted": deleted_tasks}


async def retention_status_summary(db_path: str) -> str:
    await init_retention_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        project_count = await _count(db, "SELECT COUNT(*) FROM project_activity WHERE retention_state = 'deletion_pending'")
        task_count = await _count(db, "SELECT COUNT(*) FROM tasks WHERE retention_state = 'deletion_pending'")
    if project_count == 0 and task_count == 0:
        return "Retention: no project/task records pending deletion."
    parts = []
    if project_count:
        parts.append(f"{project_count} project record(s)")
    if task_count:
        parts.append(f"{task_count} task record(s)")
    return f"Retention warning: {', '.join(parts)} pending hard deletion after the 7-day warning window."


async def run_retention_cleanup(db_path: str, now: datetime | str | None = None) -> dict[str, int]:
    marked = await mark_retention_candidates(db_path, now)
    deleted = await delete_expired_retention_candidates(db_path, now)
    return {**marked, **deleted}


async def _fetch_all(db: aiosqlite.Connection, query: str, params: tuple = ()) -> list[aiosqlite.Row]:
    cursor = await db.execute(query, params)
    return await cursor.fetchall()


async def _count(db: aiosqlite.Connection, query: str) -> int:
    cursor = await db.execute(query)
    row = await cursor.fetchone()
    return int(row[0]) if row else 0


def _timestamp(value: datetime | str | None) -> str:
    if isinstance(value, str):
        return value.replace("T", " ")[:19]
    return _datetime(value).strftime("%Y-%m-%d %H:%M:%S")


def _datetime(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now()
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    cleaned = value.replace("T", " ").replace("Z", "").split("+", 1)[0][:19]
    return datetime.fromisoformat(cleaned)
