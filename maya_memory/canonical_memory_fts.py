from __future__ import annotations

import aiosqlite

from canonical_memory_text import memory_tokens

# BM25 rank bonus for the best FTS hit; decays by rank. Kept comparable to
# activation_score units (overlap token = 10, pinned = 30).
_TOP_BONUS = 12


async def ensure_canonical_memory_fts(db: aiosqlite.Connection) -> bool:
    """Create the FTS5 index and sync triggers. Returns False when the local
    SQLite build has no FTS5 support; callers fall back to token overlap.

    Tokenizer is unicode61 on purpose: porter stemming is English-only and
    quietly degrades Malay/Manglish recall.
    """
    try:
        await db.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS canonical_memory_fts
            USING fts5(memory_id UNINDEXED, subject_key, content, tokenize='unicode61')
            """
        )
    except aiosqlite.OperationalError:
        return False
    await db.execute(
        """
        CREATE TRIGGER IF NOT EXISTS canonical_memory_fts_ai
        AFTER INSERT ON canonical_memory_items BEGIN
            DELETE FROM canonical_memory_fts WHERE memory_id = new.memory_id;
            INSERT INTO canonical_memory_fts (memory_id, subject_key, content)
            VALUES (new.memory_id, new.subject_key, new.content);
        END
        """
    )
    await db.execute(
        """
        CREATE TRIGGER IF NOT EXISTS canonical_memory_fts_au
        AFTER UPDATE OF content, subject_key ON canonical_memory_items BEGIN
            DELETE FROM canonical_memory_fts WHERE memory_id = old.memory_id;
            INSERT INTO canonical_memory_fts (memory_id, subject_key, content)
            VALUES (new.memory_id, new.subject_key, new.content);
        END
        """
    )
    await db.execute(
        """
        CREATE TRIGGER IF NOT EXISTS canonical_memory_fts_ad
        AFTER DELETE ON canonical_memory_items BEGIN
            DELETE FROM canonical_memory_fts WHERE memory_id = old.memory_id;
        END
        """
    )
    await db.execute(
        """
        INSERT INTO canonical_memory_fts (memory_id, subject_key, content)
        SELECT memory_id, subject_key, content FROM canonical_memory_items
        WHERE memory_id NOT IN (SELECT memory_id FROM canonical_memory_fts)
        """
    )
    return True


async def fts_rank_bonuses(db: aiosqlite.Connection, query: str, limit: int = 24) -> dict[str, int]:
    """BM25-ranked candidate memory_ids for a query, as score bonuses.

    Status filtering is the caller's job: results are joined against active
    rows there, so forgotten/expired rows never surface through this path.
    """
    tokens = sorted(memory_tokens(query))
    if not tokens:
        return {}
    match = " OR ".join(f'"{token}"' for token in tokens)
    try:
        cursor = await db.execute(
            """
            SELECT memory_id FROM canonical_memory_fts
            WHERE canonical_memory_fts MATCH ?
            ORDER BY bm25(canonical_memory_fts)
            LIMIT ?
            """,
            (match, limit),
        )
    except aiosqlite.OperationalError:
        return {}
    rows = await cursor.fetchall()
    return {str(row[0]): max(_TOP_BONUS - index, 1) for index, row in enumerate(rows)}
