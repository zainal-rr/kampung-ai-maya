from __future__ import annotations

import aiosqlite


async def init_skill_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS skills (
                skill_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                safety TEXT DEFAULT 'safe',
                approval_mode TEXT DEFAULT 'none',
                status TEXT DEFAULT 'active',
                source TEXT DEFAULT 'built_in',
                scaffold_path TEXT DEFAULT '',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_proposals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id TEXT NOT NULL,
                request_text TEXT NOT NULL,
                summary TEXT NOT NULL,
                research_hint TEXT DEFAULT '',
                status TEXT DEFAULT 'draft',
                scaffold_path TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS skill_usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_id TEXT NOT NULL,
                name TEXT NOT NULL,
                query TEXT NOT NULL,
                lane TEXT DEFAULT '',
                reason TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def upsert_skill(
    db_path: str,
    skill_id: str,
    name: str,
    description: str,
    safety: str,
    approval_mode: str,
    status: str,
    source: str,
    scaffold_path: str = "",
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO skills (
                skill_id, name, description, safety, approval_mode,
                status, source, scaffold_path, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(skill_id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                safety = excluded.safety,
                approval_mode = excluded.approval_mode,
                status = excluded.status,
                source = excluded.source,
                scaffold_path = excluded.scaffold_path,
                updated_at = CURRENT_TIMESTAMP
            """,
            (skill_id, name, description, safety, approval_mode, status, source, scaffold_path),
        )
        await db.commit()


async def list_custom_skills(db_path: str, limit: int = 20, status: str | None = None) -> list[dict[str, str]]:
    where = "WHERE status = ?" if status else ""
    params: tuple[str | int, ...] = (status, limit) if status else (limit,)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT skill_id, name, description, safety, approval_mode, status, source, scaffold_path
            FROM skills
            {where}
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            params,
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def update_skill_status(db_path: str, skill_id: str, status: str) -> bool:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            UPDATE skills
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE skill_id = ?
            """,
            (status, skill_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def find_skill(db_path: str, query: str) -> dict[str, str] | None:
    wanted = _norm(query)
    rows = await list_custom_skills(db_path, limit=100)
    scored = []
    for row in rows:
        raw = f"{row['skill_id']} {row['name']}".lower()
        haystack = _norm(raw)
        if wanted and (wanted in haystack or haystack in wanted):
            return row
        score = sum(1 for token in _tokens(query) if token in raw or token.rstrip("ing") in raw)
        if score:
            scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1] if scored else None


async def record_skill_usage(
    db_path: str,
    *,
    skill_id: str,
    name: str,
    query: str,
    lane: str = "",
    reason: str = "",
) -> None:
    await init_skill_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO skill_usage_events (skill_id, name, query, lane, reason)
            VALUES (?, ?, ?, ?, ?)
            """,
            (skill_id, name, query, lane, reason),
        )
        await db.commit()


async def latest_skill_usage(db_path: str, limit: int = 5) -> list[dict[str, str]]:
    await init_skill_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT skill_id, name, query, lane, reason, created_at
            FROM skill_usage_events
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def create_skill_proposal(
    db_path: str,
    skill_id: str,
    request_text: str,
    summary: str,
    research_hint: str = "",
    scaffold_path: str = "",
) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO skill_proposals (skill_id, request_text, summary, research_hint, scaffold_path)
            VALUES (?, ?, ?, ?, ?)
            """,
            (skill_id, request_text, summary, research_hint, scaffold_path),
        )
        await db.commit()
        return int(cursor.lastrowid)


async def list_skill_proposals(db_path: str, limit: int = 10) -> list[dict[str, str]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, skill_id, request_text, summary, research_hint, status, scaffold_path, created_at
            FROM skill_proposals
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


def _norm(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _tokens(text: str) -> set[str]:
    return {token for token in text.lower().split() if len(token) >= 4}
