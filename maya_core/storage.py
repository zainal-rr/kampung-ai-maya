from __future__ import annotations

import aiosqlite

from maya_documents.artifact_sessions import init_artifact_sessions_db
from maya_memory.canonical_memory import init_canonical_memory_db
from maya_memory.memory_audit import init_memory_audit_db
from maya_memory.memory_canaries import init_memory_canary_db
from maya_core.retention_policy import init_retention_db
from telegram_delivery_log import init_telegram_delivery_log_db
from telegram_turn_log import init_telegram_turn_log_db
from storage_tasks import (
    cancel_matching_tasks,
    claim_due_tasks,
    complete_task,
    create_task,
    fail_task,
    list_tasks,
    record_task_event,
    update_task_status,
)
from voice_session_log import init_voice_session_log_db


async def init_db(db_path: str) -> None:
    await init_artifact_sessions_db(db_path)
    await init_canonical_memory_db(db_path)
    await init_memory_audit_db(db_path)
    await init_memory_canary_db(db_path)
    await init_voice_session_log_db(db_path)
    await init_telegram_delivery_log_db(db_path)
    await init_telegram_turn_log_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                user_id INTEGER,
                role TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS shadow_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                error TEXT,
                fix TEXT,
                participant TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                content TEXT,
                tags TEXT
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                source TEXT DEFAULT 'user',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                details TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 2,
                channel TEXT DEFAULT 'imac',
                action_type TEXT DEFAULT 'follow_up',
                autonomy_mode TEXT DEFAULT 'suggest',
                payload TEXT DEFAULT '',
                due_at TEXT,
                last_error TEXT DEFAULT '',
                result TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS task_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                event TEXT NOT NULL,
                details TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lane TEXT NOT NULL,
                units REAL NOT NULL,
                details TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS route_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                input_type TEXT NOT NULL,
                lane TEXT NOT NULL,
                reason TEXT NOT NULL,
                cost_recorded INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        try:
            await db.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS session_search
                USING fts5(role, content, channel, created_at UNINDEXED)
                """
            )
        except aiosqlite.OperationalError:
            pass
        await db.commit()
    await init_retention_db(db_path)


async def get_history(db_path: str, user_id: int, limit: int = 10) -> list[dict[str, str]]:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT role, content FROM history WHERE user_id = ? ORDER BY rowid DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
    return [{"role": row[0], "content": row[1]} for row in reversed(rows)]


async def save_history_message(
    db_path: str,
    user_id: int,
    role: str,
    content: str,
    channel: str = "",
    *,
    source: str | None = None,
    untrusted_influence: bool = False,
    injection_detected: bool = False,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO history (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content),
        )
        try:
            await db.execute(
                "INSERT INTO session_search (role, content, channel, created_at) VALUES (?, ?, ?, datetime('now'))",
                (role, content, channel),
            )
        except aiosqlite.OperationalError:
            pass
        await db.commit()
    # Context-window turn store (docs/context_window_design_2026-06-12.md).
    # save_history_message is the single funnel every turn already flows
    # through, so the window's turn store extends it rather than creating a
    # parallel write path. No-op while MAYA_CONTEXT_WINDOW=0 (default).
    from maya_core.context_window import record_context_turn

    await record_context_turn(
        db_path,
        channel=channel or "unknown",
        role=role,
        content=content,
        source=source,
        untrusted_influence=untrusted_influence,
        injection_detected=injection_detected,
    )


async def add_knowledge_chunk(
    db_path: str,
    content: str,
    category: str = "omi_transcript",
    tags: str = "",
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO knowledge_base (category, content, tags) VALUES (?, ?, ?)",
            (category, content, tags),
        )
        await db.commit()


async def upsert_preference(db_path: str, key: str, value: str, source: str = "user") -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO preferences (key, value, source, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                source = excluded.source,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value, source),
        )
        await db.commit()


async def list_preferences(db_path: str, limit: int = 10) -> list[dict[str, str]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT key, value, source, updated_at
            FROM preferences
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_preference(db_path: str, key: str) -> str | None:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = await cursor.fetchone()
    return row[0] if row else None


async def delete_preference(db_path: str, key: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM preferences WHERE key = ?", (key,))
        await db.commit()
