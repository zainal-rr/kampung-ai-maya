from __future__ import annotations

"""Association edges between canonical memories (spreading activation).

Additive module: nothing imports this yet. The link table is the human
"one memory triggers another" mechanism. Two governance rules are enforced
here, not left to callers:

1. Links may only connect *active* canonical memories. A link to a
   forgotten, expired, superseded, or archived row is never created, and
   `expand_with_neighbors` joins against active rows only, so links can
   never become a side door around forget semantics.
2. Links are derived data, not truth. Dropping the whole table loses no
   facts; nightly consolidation can rebuild it.
"""

import aiosqlite

VALID_RELATIONS = ("related", "same_episode", "shared_entity", "causal")
DEFAULT_NEIGHBOR_LIMIT = 5

_INITIALIZED: set[str] = set()


async def init_memory_links_db(db_path: str) -> None:
    if db_path in _INITIALIZED:
        return
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_links (
                link_id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_memory_id TEXT NOT NULL,
                target_memory_id TEXT NOT NULL,
                relation TEXT NOT NULL DEFAULT 'related',
                weight REAL NOT NULL DEFAULT 1.0,
                source_channel TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_reinforced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source_memory_id, target_memory_id, relation)
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_links_source
            ON memory_links(source_memory_id, weight DESC)
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_links_target
            ON memory_links(target_memory_id, weight DESC)
            """
        )
        await db.commit()
    _INITIALIZED.add(db_path)


async def add_memory_link(
    db_path: str,
    source_memory_id: str,
    target_memory_id: str,
    *,
    relation: str = "related",
    weight: float = 1.0,
    source_channel: str = "",
) -> bool:
    """Create or reinforce a link. Returns False when the link is invalid.

    Invalid means: self-link, unknown relation, or either endpoint is not an
    active canonical memory. Re-adding an existing link reinforces its weight
    instead of duplicating it (repetition strengthens association).
    """
    if not source_memory_id or not target_memory_id or source_memory_id == target_memory_id:
        return False
    if relation not in VALID_RELATIONS:
        return False
    await init_memory_links_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        active = await _active_ids(db, (source_memory_id, target_memory_id))
        if len(active) != 2:
            return False
        await db.execute(
            """
            INSERT INTO memory_links (source_memory_id, target_memory_id, relation, weight, source_channel)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_memory_id, target_memory_id, relation) DO UPDATE SET
                weight = weight + 0.5,
                last_reinforced_at = CURRENT_TIMESTAMP
            """,
            (source_memory_id, target_memory_id, relation, max(weight, 0.1), source_channel),
        )
        await db.commit()
    return True


async def links_for(db_path: str, memory_id: str, limit: int = 10) -> list[dict[str, str | float]]:
    """Outgoing and incoming links for one memory, strongest first."""
    await init_memory_links_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT source_memory_id, target_memory_id, relation, weight
            FROM memory_links
            WHERE source_memory_id = ? OR target_memory_id = ?
            ORDER BY weight DESC, link_id DESC
            LIMIT ?
            """,
            (memory_id, memory_id, limit),
        )
        return [dict(row) for row in await cursor.fetchall()]


async def expand_with_neighbors(
    db_path: str,
    memory_ids: list[str],
    limit: int = DEFAULT_NEIGHBOR_LIMIT,
) -> list[tuple[str, str]]:
    """One hop of spreading activation: (memory_id, content) neighbors.

    Joins against canonical_memory_items with status='active' and an
    unexpired clock, so forgotten facts can never surface through links.
    Seed ids are excluded from the result. Intended future call site:
    search_relevant_canonical_memories, as a post-selection boost.
    """
    seeds = [memory_id for memory_id in memory_ids if memory_id]
    if not seeds:
        return []
    await init_memory_links_db(db_path)
    placeholders = ",".join("?" for _ in seeds)
    query = f"""
        SELECT DISTINCT
            CASE WHEN links.source_memory_id IN ({placeholders})
                 THEN links.target_memory_id ELSE links.source_memory_id END AS neighbor_id,
            items.content,
            MAX(links.weight) AS best_weight
        FROM memory_links AS links
        JOIN canonical_memory_items AS items
          ON items.memory_id = CASE WHEN links.source_memory_id IN ({placeholders})
                                    THEN links.target_memory_id ELSE links.source_memory_id END
        WHERE (links.source_memory_id IN ({placeholders}) OR links.target_memory_id IN ({placeholders}))
          AND items.status = 'active'
          AND (items.expires_at IS NULL OR items.expires_at > datetime('now'))
          AND items.temporary = 0
          AND items.test_marker = 0
        GROUP BY neighbor_id, items.content
        ORDER BY best_weight DESC
        LIMIT ?
    """
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(query, (*seeds, *seeds, *seeds, *seeds, limit + len(seeds)))
        rows = await cursor.fetchall()
    seen = set(seeds)
    neighbors: list[tuple[str, str]] = []
    for neighbor_id, content, _weight in rows:
        if neighbor_id in seen:
            continue
        seen.add(neighbor_id)
        neighbors.append((str(neighbor_id), str(content)))
        if len(neighbors) >= limit:
            break
    return neighbors


async def _active_ids(db: aiosqlite.Connection, memory_ids: tuple[str, ...]) -> set[str]:
    # temporary/test rows are excluded at both ends: links to them cannot be
    # created here, and expand_with_neighbors filters them at read time too.
    # The lexical path deliberately keeps zero-overlap temporary rows out of
    # context; association must not reopen that door.
    placeholders = ",".join("?" for _ in memory_ids)
    cursor = await db.execute(
        f"""
        SELECT memory_id FROM canonical_memory_items
        WHERE memory_id IN ({placeholders})
          AND status = 'active'
          AND (expires_at IS NULL OR expires_at > datetime('now'))
          AND temporary = 0
          AND test_marker = 0
        """,
        memory_ids,
    )
    return {str(row[0]) for row in await cursor.fetchall()}
