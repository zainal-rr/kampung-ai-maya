from __future__ import annotations

import aiosqlite


async def init_lesson_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_text TEXT NOT NULL,
                normalized_rule TEXT NOT NULL,
                lesson_type TEXT DEFAULT 'preference',
                scope TEXT DEFAULT 'global',
                trigger TEXT DEFAULT 'explicit',
                confidence TEXT DEFAULT 'high',
                status TEXT DEFAULT 'active',
                channel TEXT DEFAULT 'telegram',
                preference_key TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_lessons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_text TEXT NOT NULL,
                normalized_rule TEXT NOT NULL,
                lesson_type TEXT DEFAULT 'preference',
                scope TEXT DEFAULT 'global',
                channel TEXT DEFAULT 'telegram',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def add_lesson(
    db_path: str,
    raw_text: str,
    normalized_rule: str,
    lesson_type: str,
    scope: str,
    trigger: str,
    confidence: str,
    channel: str,
    preference_key: str = "",
) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO lessons (
                raw_text, normalized_rule, lesson_type, scope,
                trigger, confidence, channel, preference_key
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (raw_text, normalized_rule, lesson_type, scope, trigger, confidence, channel, preference_key),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def get_lesson(db_path: str, lesson_id: int) -> dict[str, str | int] | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
        row = await cursor.fetchone()
    return dict(row) if row else None


async def add_pending_lesson(
    db_path: str,
    raw_text: str,
    normalized_rule: str,
    lesson_type: str,
    scope: str,
    channel: str,
) -> int:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM pending_lessons WHERE channel = ?", (channel,))
        cursor = await db.execute(
            """
            INSERT INTO pending_lessons (raw_text, normalized_rule, lesson_type, scope, channel)
            VALUES (?, ?, ?, ?, ?)
            """,
            (raw_text, normalized_rule, lesson_type, scope, channel),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def get_pending_lesson(db_path: str, channel: str) -> dict[str, str | int] | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM pending_lessons
            WHERE channel = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (channel,),
        )
        row = await cursor.fetchone()
    return dict(row) if row else None


async def clear_pending_lesson(db_path: str, pending_id: int) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM pending_lessons WHERE id = ?", (pending_id,))
        await db.commit()


async def list_lessons(db_path: str, limit: int = 8) -> list[dict[str, str | int]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT *
            FROM lessons
            WHERE status = 'active'
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def search_lessons(db_path: str, query: str, limit: int = 5) -> list[str]:
    lowered = query.lower()
    lessons = await list_lessons(db_path, limit=30)
    scored = []
    for item in lessons:
        haystack = f"{item['normalized_rule']} {item['lesson_type']} {item['scope']}".lower()
        score = sum(1 for token in _tokens(lowered) if token in haystack)
        if _story_query(lowered) and item["scope"] == "story":
            score += 4
        if _language_query(lowered) and item["scope"] in {"language", "story"}:
            score += 3
        if score > 0:
            scored.append((score, str(item["normalized_rule"])))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [value for _, value in scored[:limit]]


def _tokens(text: str) -> set[str]:
    return {token for token in text.split() if len(token) >= 4}


def _story_query(text: str) -> bool:
    return any(marker in text for marker in ("story", "cerita", "karang"))


def _language_query(text: str) -> bool:
    return any(marker in text for marker in ("malay", "manglish", "melayu", "bahasa"))
