from __future__ import annotations

import aiosqlite

from maya_core.permission_policy import contains_sensitive_info


KINDS = {
    "what_worked", "what_failed", "user_preference", "example",
    "test_case", "safe_data_note", "blocked_data_note",
}
STATUSES = {"active", "stale", "rejected", "disabled"}
BLOCKED_MARKERS = (
    "passport", "identity number", "ic number", "kad pengenalan",
    "card number", "credit card", "debit card", "bank account",
    "login", "password", "otp", "2fa", "private identifier",
)


async def init_skill_memory_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_memory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                confidence REAL DEFAULT 0.8,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def add_skill_memory(
    db_path: str,
    *,
    skill_id: str,
    kind: str,
    content: str,
    source: str = "manual",
    confidence: float = 0.8,
    status: str = "active",
) -> tuple[bool, str]:
    await init_skill_memory_db(db_path)
    if _blocked_content(content):
        return False, "Blocked sensitive or private skill memory."
    clean_kind = kind if kind in KINDS else "example"
    clean_status = status if status in STATUSES else "active"
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO skill_memory_items (
                skill_id, kind, content, source, confidence, status, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (skill_id, clean_kind, content[:1000], source[:120], confidence, clean_status),
        )
        await db.commit()
    return True, "Skill memory saved."


async def list_skill_memory(db_path: str, skill_id: str, include_disabled: bool = False) -> list[dict[str, str]]:
    await init_skill_memory_db(db_path)
    query = """
        SELECT id, skill_id, kind, content, source, confidence, status, created_at, updated_at
        FROM skill_memory_items
        WHERE skill_id = ?
        ORDER BY updated_at DESC, id DESC
        LIMIT 20
    """
    if not include_disabled:
        query = """
            SELECT id, skill_id, kind, content, source, confidence, status, created_at, updated_at
            FROM skill_memory_items
            WHERE skill_id = ? AND status = 'active'
            ORDER BY updated_at DESC, id DESC
            LIMIT 20
        """
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, (skill_id,))
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def disable_skill_memory(db_path: str, skill_id: str, query: str = "") -> int:
    await init_skill_memory_db(db_path)
    if query:
        pattern = f"%{query}%"
        sql = """
            UPDATE skill_memory_items
            SET status = 'disabled', updated_at = CURRENT_TIMESTAMP
            WHERE skill_id = ? AND content LIKE ? AND status = 'active'
        """
        params: tuple[str, ...] = (skill_id, pattern)
    else:
        sql = """
            UPDATE skill_memory_items
            SET status = 'disabled', updated_at = CURRENT_TIMESTAMP
            WHERE skill_id = ? AND status = 'active'
        """
        params = (skill_id,)
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(sql, params)
        await db.commit()
        return int(cursor.rowcount)


def _blocked_content(content: str) -> bool:
    lowered = " ".join(content.lower().split())
    return contains_sensitive_info(content) or any(marker in lowered for marker in BLOCKED_MARKERS)
