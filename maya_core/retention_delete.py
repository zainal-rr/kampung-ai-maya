from __future__ import annotations

import hashlib

import aiosqlite


async def delete_project_records(db: aiosqlite.Connection, project_path: str, project_name: str) -> None:
    await db.execute("DELETE FROM project_memories WHERE project_path = ?", (project_path,))
    await db.execute("DELETE FROM project_activity WHERE project_path = ?", (project_path,))
    await _delete_preference_if_value(db, "active_project_path", project_path)
    await _delete_preference_if_value(db, "active_project_name", project_name)
    await _delete_harness_runs(db, await _harness_runs_for_project(db, project_path, project_name))
    await _delete_session_search_matches(db, [project_path, project_name])
    await _insert_tombstone(db, "project", project_path, "90-day inactivity retention")


async def delete_task_records(db: aiosqlite.Connection, task_id: int, title: str, details: str) -> None:
    await db.execute("DELETE FROM task_events WHERE task_id = ?", (task_id,))
    await db.execute("DELETE FROM workflow_runs WHERE task_id = ?", (task_id,))
    await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    await _delete_harness_runs(db, await _harness_runs_for_task(db, task_id))
    await _delete_session_search_matches(db, [title, details])
    await _insert_tombstone(db, "task", f"task:{task_id}", "90-day inactivity retention")


async def _harness_runs_for_project(db: aiosqlite.Connection, project_path: str, project_name: str) -> list[str]:
    patterns = [f"%{project_path}%"]
    if project_name:
        patterns.append(f"%{project_name}%")
    run_ids: set[str] = set()
    for pattern in patterns:
        try:
            rows = await _fetch_all(
                db,
                "SELECT run_id FROM harness_runs WHERE state_json LIKE ? OR goal LIKE ?",
                (pattern, pattern),
            )
        except aiosqlite.OperationalError:
            return []
        run_ids.update(str(row["run_id"]) for row in rows)
    return sorted(run_ids)


async def _harness_runs_for_task(db: aiosqlite.Connection, task_id: int) -> list[str]:
    patterns = (f"harness:background:{task_id}", f"%\"task_id\": {task_id}%", f"%\"task_id\":\"{task_id}\"%")
    try:
        rows = await _fetch_all(
            db,
            """
            SELECT run_id
            FROM harness_runs
            WHERE thread_id = ? OR state_json LIKE ? OR state_json LIKE ?
            """,
            patterns,
        )
    except aiosqlite.OperationalError:
        return []
    return [str(row["run_id"]) for row in rows]


async def _delete_harness_runs(db: aiosqlite.Connection, run_ids: list[str]) -> None:
    if not run_ids:
        return
    placeholders = ", ".join("?" for _ in run_ids)
    for table in ("harness_events", "harness_artifacts", "harness_approvals", "harness_observations", "harness_runs"):
        try:
            await db.execute(f"DELETE FROM {table} WHERE run_id IN ({placeholders})", tuple(run_ids))
        except aiosqlite.OperationalError:
            pass


async def _delete_session_search_matches(db: aiosqlite.Connection, values: list[str]) -> None:
    needles = [value for value in values if value and len(value.strip()) >= 3]
    if not needles:
        return
    try:
        rows = await _fetch_all(db, "SELECT rowid, content FROM session_search")
    except aiosqlite.OperationalError:
        return
    rowids = [row["rowid"] for row in rows if any(needle in str(row["content"]) for needle in needles)]
    for rowid in rowids:
        await db.execute("DELETE FROM session_search WHERE rowid = ?", (rowid,))


async def _delete_preference_if_value(db: aiosqlite.Connection, key: str, value: str) -> None:
    if value:
        await db.execute("DELETE FROM preferences WHERE key = ? AND value = ?", (key, value))


async def _insert_tombstone(db: aiosqlite.Connection, object_type: str, key: str, reason: str) -> None:
    await db.execute(
        "INSERT INTO retention_tombstones (object_type, object_key_hash, reason) VALUES (?, ?, ?)",
        (object_type, hashlib.sha256(key.encode("utf-8")).hexdigest()[:20], reason),
    )


async def _fetch_all(db: aiosqlite.Connection, query: str, params: tuple = ()) -> list[aiosqlite.Row]:
    cursor = await db.execute(query, params)
    return await cursor.fetchall()
