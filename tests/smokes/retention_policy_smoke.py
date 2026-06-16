from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import aiosqlite

from maya_harness.harness_observation_store import record_observation
from maya_harness.harness_models import GroundedObservation
from maya_harness.harness_store import init_harness_db, record_artifact, record_event, upsert_run
from maya_core.lesson_store import init_lesson_db
from maya_core.retention_policy import (
    DELETION_PENDING,
    delete_expired_retention_candidates,
    mark_retention_candidates,
    retention_status_summary,
    touch_project_activity,
)
from maya_core.session_search import index_session_message, search_sessions
from maya_core.storage import create_task, init_db, record_task_event
from weekly_memory import WeeklyMemoryDistiller
from workflow_store import begin_workflow


NOW = datetime(2026, 5, 28, 12, 0, 0)


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-retention-") as tmp:
        root = Path(tmp)
        db_path = str(root / "smoke.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        await init_harness_db(db_path)
        project = root / "projects" / "kyoto-plan"
        project.mkdir(parents=True)
        (project / "README.md").write_text("Keep this file.", encoding="utf-8")

        await _project_89_days_stays_active(db_path, project)
        await _project_pending_then_touch_renews(db_path, project)
        await _project_records_delete_without_files(db_path, project)
        await _task_records_delete_with_workflows(db_path)
        await _weekly_memory_excludes_pending_tasks(db_path)
    print("retention_policy_smoke: ok")


async def _project_89_days_stays_active(db_path: str, project: Path) -> None:
    await touch_project_activity(db_path, project, "recent enough", "smoke", NOW - timedelta(days=89))
    result = await mark_retention_candidates(db_path, NOW)
    _require(result["projects_marked"] == 0, "89-day project should not be marked")
    _require(await _project_state(db_path, project) == "active", "89-day project should stay active")


async def _project_pending_then_touch_renews(db_path: str, project: Path) -> None:
    await _set_project_activity(db_path, project, NOW - timedelta(days=90, seconds=1))
    result = await mark_retention_candidates(db_path, NOW)
    _require(result["projects_marked"] == 1, "90-day project should be marked pending")
    _require(await _project_state(db_path, project) == DELETION_PENDING, "project should be pending")
    warning = await retention_status_summary(db_path)
    _require("project record" in warning.lower(), "retention warning should mention pending project")
    await touch_project_activity(db_path, project, "talked about it", "smoke", NOW)
    _require(await _project_state(db_path, project) == "active", "talk/edit should renew project")


async def _project_records_delete_without_files(db_path: str, project: Path) -> None:
    await touch_project_activity(db_path, project, "old project", "smoke", NOW - timedelta(days=98))
    await _insert_project_memory(db_path, project, "decision", "Stay near Gion.")
    await index_session_message(db_path, "user", f"talked about {project}", "telegram")
    run_id = "hrn_project_old"
    await upsert_run(
        db_path,
        {
            "run_id": run_id,
            "thread_id": f"harness:{run_id}",
            "workflow_type": "project",
            "goal": f"work on {project.name}",
            "state_json": json.dumps({"active_project_path": str(project)}),
        },
    )
    await record_event(db_path, run_id, "started", str(project))
    await record_artifact(db_path, run_id, "document", str(project / "README.md"), "old project file")
    await record_observation(db_path, run_id, GroundedObservation(source="smoke", text_summary="project visible", confidence=1))
    await mark_retention_candidates(db_path, NOW)
    await _set_project_pending_at(db_path, project, NOW - timedelta(days=8))
    deleted = await delete_expired_retention_candidates(db_path, NOW)
    _require(deleted["projects_deleted"] == 1, "expired project records should be deleted")
    _require((project / "README.md").exists(), "retention must not delete local files")
    _require(await _count(db_path, "SELECT COUNT(*) FROM project_memories") == 0, "project memory survived deletion")
    _require(await _count(db_path, "SELECT COUNT(*) FROM project_activity") == 0, "project activity survived deletion")
    _require(await _count(db_path, "SELECT COUNT(*) FROM harness_runs WHERE run_id = ?", (run_id,)) == 0, "harness run survived")
    _require(not await search_sessions(db_path, str(project)), "project session search rows survived")
    _require(await _count(db_path, "SELECT COUNT(*) FROM retention_tombstones WHERE object_type = 'project'") == 1, "project tombstone missing")


async def _task_records_delete_with_workflows(db_path: str) -> None:
    task_id = await create_task(db_path, "ancient project follow-up", details="old inactive task", channel="telegram")
    await begin_workflow(db_path, task_id, ["step one"])
    await record_task_event(db_path, task_id, "note", "old note")
    await index_session_message(db_path, "assistant", "ancient project follow-up", "telegram")
    run_id = "hrn_task_old"
    await upsert_run(
        db_path,
        {
            "run_id": run_id,
            "thread_id": f"harness:background:{task_id}",
            "workflow_type": "scheduled",
            "goal": "ancient project follow-up",
            "state_json": json.dumps({"task_id": task_id}),
        },
    )
    await _set_task_activity(db_path, task_id, NOW - timedelta(days=98))
    await mark_retention_candidates(db_path, NOW)
    await _set_task_pending_at(db_path, task_id, NOW - timedelta(days=8))
    deleted = await delete_expired_retention_candidates(db_path, NOW)
    _require(deleted["tasks_deleted"] == 1, "expired task should be deleted")
    _require(await _count(db_path, "SELECT COUNT(*) FROM tasks WHERE id = ?", (task_id,)) == 0, "task survived")
    _require(await _count(db_path, "SELECT COUNT(*) FROM task_events WHERE task_id = ?", (task_id,)) == 0, "task events survived")
    _require(await _count(db_path, "SELECT COUNT(*) FROM workflow_runs WHERE task_id = ?", (task_id,)) == 0, "workflow survived")
    _require(await _count(db_path, "SELECT COUNT(*) FROM harness_runs WHERE run_id = ?", (run_id,)) == 0, "task harness survived")
    _require(not await search_sessions(db_path, "ancient project follow-up"), "task search row survived")


async def _weekly_memory_excludes_pending_tasks(db_path: str) -> None:
    task_id = await create_task(db_path, "do not revive ancient context", channel="telegram")
    await _set_task_activity(db_path, task_id, NOW - timedelta(days=91))
    report = await WeeklyMemoryDistiller(db_path).run(save=False, now=NOW)
    _require("do not revive ancient context" not in report.summary, "weekly memory revived stale task")
    _require(await _task_state(db_path, task_id) == DELETION_PENDING, "weekly memory should mark stale task pending")


async def _insert_project_memory(db_path: str, project: Path, kind: str, content: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO project_memories (project_path, kind, content, source) VALUES (?, ?, ?, 'smoke')",
            (str(project.resolve(strict=False)), kind, content),
        )
        await db.commit()


async def _set_project_activity(db_path: str, project: Path, timestamp: datetime) -> None:
    await touch_project_activity(db_path, project, "set old", "smoke", timestamp)


async def _set_project_pending_at(db_path: str, project: Path, timestamp: datetime) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE project_activity SET deletion_pending_at = ? WHERE project_path = ?",
            (_ts(timestamp), str(project.resolve(strict=False))),
        )
        await db.commit()


async def _set_task_activity(db_path: str, task_id: int, timestamp: datetime) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE tasks SET updated_at = ?, retention_state = 'active', deletion_pending_at = NULL WHERE id = ?",
            (_ts(timestamp), task_id),
        )
        await db.commit()


async def _set_task_pending_at(db_path: str, task_id: int, timestamp: datetime) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE tasks SET deletion_pending_at = ? WHERE id = ?", (_ts(timestamp), task_id))
        await db.commit()


async def _project_state(db_path: str, project: Path) -> str:
    rows = await _fetch(db_path, "SELECT retention_state FROM project_activity WHERE project_path = ?", (str(project.resolve(strict=False)),))
    return str(rows[0]["retention_state"]) if rows else ""


async def _task_state(db_path: str, task_id: int) -> str:
    rows = await _fetch(db_path, "SELECT retention_state FROM tasks WHERE id = ?", (task_id,))
    return str(rows[0]["retention_state"]) if rows else ""


async def _count(db_path: str, query: str, params: tuple = ()) -> int:
    rows = await _fetch(db_path, query, params)
    return int(next(iter(rows[0].values()))) if rows else 0


async def _fetch(db_path: str, query: str, params: tuple = ()) -> list[dict]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, params)
        return [dict(row) for row in await cursor.fetchall()]


def _ts(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _require(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
