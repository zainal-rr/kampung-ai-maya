from __future__ import annotations

import json

import aiosqlite

from skill_store import init_skill_db

REQUIRED_SKILL_TESTS = {"trigger", "non_trigger", "safety", "happy_path", "failure_path", "regression", "approval"}
EVALUATION_TESTS = REQUIRED_SKILL_TESTS - {"approval"}


async def init_skill_learning_db(db_path: str) -> None:
    await init_skill_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_learning_metadata (
                skill_id TEXT PRIMARY KEY,
                triggers TEXT DEFAULT '[]',
                non_triggers TEXT DEFAULT '[]',
                tools_needed TEXT DEFAULT '[]',
                provider_lane TEXT DEFAULT '',
                safety_boundary TEXT DEFAULT '',
                test_commands TEXT DEFAULT '[]',
                review_notes TEXT DEFAULT '',
                last_failure TEXT DEFAULT '',
                disable_reason TEXT DEFAULT '',
                usage_count INTEGER DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_activation_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id TEXT NOT NULL,
                command TEXT NOT NULL,
                test_type TEXT DEFAULT 'legacy_smoke',
                status TEXT NOT NULL,
                notes TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        try:
            await db.execute("ALTER TABLE skill_activation_tests ADD COLUMN test_type TEXT DEFAULT 'legacy_smoke'")
        except aiosqlite.OperationalError:
            pass
        await db.commit()


async def upsert_skill_metadata(db_path: str, skill_id: str, **fields) -> None:
    await init_skill_learning_db(db_path)
    payload = {
        "triggers": fields.get("triggers", []),
        "non_triggers": fields.get("non_triggers", []),
        "tools_needed": fields.get("tools_needed", []),
        "provider_lane": fields.get("provider_lane", ""),
        "safety_boundary": fields.get("safety_boundary", ""),
        "test_commands": fields.get("test_commands", []),
        "review_notes": fields.get("review_notes", ""),
    }
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO skill_learning_metadata (
                skill_id, triggers, non_triggers, tools_needed, provider_lane,
                safety_boundary, test_commands, review_notes, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(skill_id) DO UPDATE SET
                triggers = excluded.triggers,
                non_triggers = excluded.non_triggers,
                tools_needed = excluded.tools_needed,
                provider_lane = excluded.provider_lane,
                safety_boundary = excluded.safety_boundary,
                test_commands = excluded.test_commands,
                review_notes = excluded.review_notes,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                skill_id,
                json.dumps(payload["triggers"]),
                json.dumps(payload["non_triggers"]),
                json.dumps(payload["tools_needed"]),
                payload["provider_lane"],
                payload["safety_boundary"],
                json.dumps(payload["test_commands"]),
                payload["review_notes"],
            ),
        )
        await db.commit()


async def record_skill_test(
    db_path: str,
    skill_id: str,
    command: str,
    status: str,
    notes: str = "",
    test_type: str = "legacy_smoke",
) -> None:
    await init_skill_learning_db(db_path)
    clean_type = test_type if test_type in REQUIRED_SKILL_TESTS else test_type or "legacy_smoke"
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO skill_activation_tests (skill_id, command, test_type, status, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (skill_id, command, clean_type, status, notes[:500]),
        )
        await db.commit()


async def skill_has_passing_test(db_path: str, skill_id: str) -> bool:
    await init_skill_learning_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT 1 FROM skill_activation_tests WHERE skill_id = ? AND status = 'passed' LIMIT 1",
            (skill_id,),
        )
        return await cursor.fetchone() is not None


async def skill_has_required_tests(db_path: str, skill_id: str) -> bool:
    await init_skill_learning_db(db_path)
    return not await missing_required_tests(db_path, skill_id)


async def missing_required_tests(db_path: str, skill_id: str) -> list[str]:
    await init_skill_learning_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT test_type, status
            FROM skill_activation_tests
            WHERE skill_id = ?
            ORDER BY id ASC
            """,
            (skill_id,),
        )
        rows = await cursor.fetchall()
    latest = {str(test_type): str(status) for test_type, status in rows}
    return sorted(test for test in REQUIRED_SKILL_TESTS if latest.get(test) != "passed")


async def mark_skill_disabled(db_path: str, skill_id: str, reason: str) -> None:
    await init_skill_learning_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE skill_learning_metadata
            SET disable_reason = ?, updated_at = CURRENT_TIMESTAMP
            WHERE skill_id = ?
            """,
            (reason[:500], skill_id),
        )
        await db.commit()


async def increment_skill_usage(db_path: str, skill_id: str) -> None:
    await init_skill_learning_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO skill_learning_metadata (skill_id, usage_count)
            VALUES (?, 1)
            ON CONFLICT(skill_id) DO UPDATE SET
                usage_count = usage_count + 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (skill_id,),
        )
        await db.commit()


async def get_skill_learning_metadata(db_path: str, skill_id: str) -> dict[str, str | int] | None:
    await init_skill_learning_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM skill_learning_metadata WHERE skill_id = ?",
            (skill_id,),
        )
        row = await cursor.fetchone()
    return dict(row) if row else None
