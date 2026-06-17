from __future__ import annotations

import aiosqlite

from maya_core.provenance import provenance_from_source_channel


async def init_session_search_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await _ensure_session_search_schema(db)
        await db.commit()


async def index_session_message(
    db_path: str,
    role: str,
    content: str,
    channel: str = "",
    *,
    source: str | None = None,
    untrusted_influence: bool = False,
    injection_detected: bool = False,
) -> None:
    if not content.strip():
        return
    source_name = (source or channel or "unknown").strip() or "unknown"
    provenance = provenance_from_source_channel(source_name)
    row_untrusted = bool(untrusted_influence or provenance.untrusted_influence)
    row_injection = bool(injection_detected or provenance.injection_detected)
    try:
        await init_session_search_db(db_path)
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                INSERT INTO session_search (
                    role, content, channel, source,
                    untrusted_influence, injection_detected, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (role, content, channel, source_name, int(row_untrusted), int(row_injection)),
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
                SELECT role, content, channel, source, untrusted_influence, injection_detected, created_at
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
        if bool(row.get("untrusted_influence")):
            source = row.get("source") or "unknown"
            text = f"{text} [reference-only; provenance: {source}; untrusted_influence: true]"
        lines.append(f"{idx}) {row['role']} on {channel}: {text}")
    return "\n".join(lines)


async def _ensure_session_search_schema(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS session_search
        USING fts5(
            role, content, channel,
            source UNINDEXED,
            untrusted_influence UNINDEXED,
            injection_detected UNINDEXED,
            created_at UNINDEXED
        )
        """
    )
    cursor = await db.execute("PRAGMA table_info(session_search)")
    columns = {str(row[1]) for row in await cursor.fetchall()}
    if {"source", "untrusted_influence", "injection_detected"} <= columns:
        return
    rows = []
    try:
        hist = await db.execute(
            """
            SELECT role, content, source, untrusted_influence, injection_detected, timestamp
            FROM history
            ORDER BY rowid
            """
        )
        rows = await hist.fetchall()
    except aiosqlite.OperationalError:
        pass
    await db.execute("DROP TABLE IF EXISTS session_search")
    await db.execute(
        """
        CREATE VIRTUAL TABLE session_search
        USING fts5(
            role, content, channel,
            source UNINDEXED,
            untrusted_influence UNINDEXED,
            injection_detected UNINDEXED,
            created_at UNINDEXED
        )
        """
    )
    for row in rows:
        await db.execute(
            """
            INSERT INTO session_search (
                role, content, channel, source,
                untrusted_influence, injection_detected, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(row[0] or ""),
                str(row[1] or ""),
                str(row[2] or "unknown"),
                str(row[2] or "unknown"),
                int(row[3] if row[3] is not None else 1),
                int(row[4] if row[4] is not None else 0),
                str(row[5] or ""),
            ),
        )
