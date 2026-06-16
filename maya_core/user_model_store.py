from __future__ import annotations

import aiosqlite

from maya_core.permission_policy import contains_sensitive_info


ALLOWED_CATEGORIES = {
    "preferences", "tone", "work_style", "recurring_worries",
    "decision_patterns", "communication_style", "skill_specific_preferences",
}
BLOCKED_MARKERS = (
    "password", "otp", "bank", "card", "private key", "api key",
    "passport", "identity number", "ic number", "seed phrase", "private",
    "creepy", "intimate", "sexual",
)


async def init_user_model_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_model_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id TEXT DEFAULT '',
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                confidence REAL DEFAULT 0.8,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        try:
            await db.execute("ALTER TABLE user_model_items ADD COLUMN skill_id TEXT DEFAULT ''")
        except aiosqlite.OperationalError:
            pass
        await db.commit()


async def add_user_model_item(
    db_path: str,
    *,
    category: str,
    content: str,
    source: str = "explicit",
    confidence: float = 0.8,
    confirmed: bool = False,
    skill_id: str = "",
) -> tuple[bool, str]:
    await init_user_model_db(db_path)
    clean_category = category if category in ALLOWED_CATEGORIES else "preferences"
    if _blocked(content):
        return False, "Blocked sensitive or over-private user model entry."
    if source not in {"explicit", "confirmed"} and not confirmed:
        return False, "I need confirmation before saving that user-model observation."
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO user_model_items (skill_id, category, content, source, confidence, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (skill_id[:120], clean_category, content[:1000], source[:120], confidence),
        )
        await db.commit()
    return True, "User model item saved."


async def list_user_model_items(db_path: str, limit: int = 12, skill_id: str = "") -> list[dict[str, str]]:
    await init_user_model_db(db_path)
    where = "status = 'active'"
    params: tuple[str | int, ...] = (limit,)
    if skill_id:
        where = "status = 'active' AND skill_id = ?"
        params = (skill_id, limit)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT skill_id, category, content, source, confidence, created_at
            FROM user_model_items
            WHERE """ + where + """
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            params,
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


def _blocked(content: str) -> bool:
    lowered = " ".join(content.lower().split())
    return contains_sensitive_info(content) or any(marker in lowered for marker in BLOCKED_MARKERS)
