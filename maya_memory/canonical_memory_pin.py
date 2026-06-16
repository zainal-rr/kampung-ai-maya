from __future__ import annotations

import aiosqlite

from canonical_memory import init_canonical_memory_db, memory_tokens, subject_key_from_text


async def set_canonical_memory_pin(db_path: str, query: str, *, pinned: bool) -> str:
    cleaned = " ".join(query.strip().split())
    action = "pin" if pinned else "unpin"
    if not cleaned:
        return f"Use /memory {action} followed by a memory ID or memory text."
    matches = await _matching_memory_ids(db_path, cleaned)
    if not matches:
        return f"Memory {action} result:\n1) No active canonical memory matched: {cleaned}"
    async with aiosqlite.connect(db_path) as db:
        for memory_id, _content in matches:
            await db.execute(
                """
                UPDATE canonical_memory_items
                SET pinned = ?, updated_at = CURRENT_TIMESTAMP
                WHERE memory_id = ?
                """,
                (1 if pinned else 0, memory_id),
            )
        await db.commit()
    verb = "Pinned" if pinned else "Unpinned"
    lines = [f"Memory {action} result:", f"1) {verb} {len(matches)} canonical memory record(s)."]
    lines.extend(f"{idx}) {content}" for idx, (_memory_id, content) in enumerate(matches[:3], start=2))
    return "\n".join(lines)


async def _matching_memory_ids(db_path: str, query: str) -> list[tuple[str, str]]:
    await init_canonical_memory_db(db_path)
    subject_key = subject_key_from_text(query)
    tokens = memory_tokens(query)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await (
            await db.execute(
                """
                SELECT memory_id, subject_key, content
                FROM canonical_memory_items
                WHERE status = 'active'
                ORDER BY pinned DESC, updated_at DESC
                LIMIT 120
                """
            )
        ).fetchall()
    matches: list[tuple[str, str]] = []
    for row in rows:
        memory_id = str(row["memory_id"])
        content = str(row["content"])
        haystack = f"{row['subject_key']} {content}"
        if query == memory_id or (subject_key and row["subject_key"] == subject_key):
            matches.append((memory_id, content))
        elif tokens and tokens.issubset(memory_tokens(haystack)):
            matches.append((memory_id, content))
    return matches
