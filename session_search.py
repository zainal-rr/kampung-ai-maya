from __future__ import annotations

import aiosqlite


async def init_session_search_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS session_search
            USING fts5(role, content, channel, created_at UNINDEXED)
            """
        )
        await db.commit()


async def index_session_message(db_path: str, role: str, content: str, channel: str = "") -> None:
    if not content.strip():
        return
    try:
        await init_session_search_db(db_path)
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT INTO session_search (role, content, channel, created_at) VALUES (?, ?, ?, datetime('now'))",
                (role, content, channel),
            )
            await db.commit()
    except aiosqlite.OperationalError:
        return


async def search_sessions(db_path: str, query: str, limit: int = 5) -> list[dict[str, str]]:
    cleaned = " ".join(query.strip().split())
    if not cleaned:
        return []
    await init_session_search_db(db_path)
    expr = " OR ".join(token.replace('"', "") for token in cleaned.split() if len(token) > 2)
    if not expr:
        expr = cleaned.replace('"', "")
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute(
                """
                SELECT role, content, channel, created_at
                FROM session_search
                WHERE session_search MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (expr, limit),
            )
            rows = await cursor.fetchall()
        except aiosqlite.OperationalError:
            rows = []
    return [dict(row) for row in rows]


def format_session_search_results(query: str, rows: list[dict[str, str]]) -> str:
    if not rows:
        return f"I could not find old session notes about {query}."
    lines = [f"Session search for {query}:"]
    for idx, row in enumerate(rows, start=1):
        text = " ".join(str(row["content"]).split())[:220]
        channel = row.get("channel") or "shared"
        lines.append(f"{idx}) {row['role']} on {channel}: {text}")
    return "\n".join(lines)
