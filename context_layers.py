from __future__ import annotations

import re
from collections import Counter

import aiosqlite

FACT_CUES = (
    "remember",
    "my preference",
    "i prefer",
    "do not",
    "don't",
    "should",
    "must",
    "api key",
    "permission",
    "telegram",
    "imac",
    "maya",
)
VIBE_WORDS = {
    "alive",
    "friend",
    "partner",
    "natural",
    "chill",
    "relational",
    "fluid",
    "simple",
    "trust",
    "local",
}


async def init_context_layers_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS context_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT DEFAULT 'general',
                fact TEXT NOT NULL UNIQUE,
                source TEXT DEFAULT 'session_compactor',
                confidence REAL DEFAULT 0.72,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS context_vibes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT DEFAULT 'general',
                vibe TEXT NOT NULL UNIQUE,
                source TEXT DEFAULT 'session_compactor',
                confidence REAL DEFAULT 0.62,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def preserve_context_layers(db_path: str, rows: list[dict[str, str]], topic: str) -> dict[str, int]:
    await init_context_layers_db(db_path)
    facts = _extract_facts(rows)
    vibes = _extract_vibes(rows, topic)
    async with aiosqlite.connect(db_path) as db:
        for fact in facts:
            await db.execute(
                """
                INSERT INTO context_facts (topic, fact, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(fact) DO UPDATE SET
                    topic = excluded.topic,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (topic, fact),
            )
        for vibe in vibes:
            await db.execute(
                """
                INSERT INTO context_vibes (topic, vibe, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(vibe) DO UPDATE SET
                    topic = excluded.topic,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (topic, vibe),
            )
        await db.commit()
    return {"facts": len(facts), "vibes": len(vibes)}


async def relevant_context_facts(db_path: str, query: str, limit: int = 6) -> list[dict[str, str | float]]:
    await init_context_layers_db(db_path)
    return await _ranked_rows(db_path, "context_facts", "fact", query, limit)


async def relevant_context_vibes(db_path: str, query: str, limit: int = 4) -> list[dict[str, str | float]]:
    await init_context_layers_db(db_path)
    return await _ranked_rows(db_path, "context_vibes", "vibe", query, limit)


async def _ranked_rows(
    db_path: str,
    table: str,
    text_column: str,
    query: str,
    limit: int,
) -> list[dict[str, str | float]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"""
            SELECT topic, {text_column} AS text, source, confidence, updated_at
            FROM {table}
            ORDER BY updated_at DESC, id DESC
            LIMIT 24
            """
        )
        rows = await cursor.fetchall()
    tokens = _tokens(query)
    scored = []
    for row in rows:
        text = str(row["text"])
        score = sum(1 for token in tokens if token in text.lower()) if tokens else 0
        scored.append((score, dict(row)))
    scored.sort(key=lambda item: (item[0], str(item[1]["updated_at"])), reverse=True)
    chosen = [item for score, item in scored if score > 0][:limit]
    return chosen or [item for _, item in scored[:limit]]


def _extract_facts(rows: list[dict[str, str]]) -> list[str]:
    facts = []
    for row in rows:
        if row.get("role") != "user":
            continue
        content = _shorten(row.get("content", ""))
        lowered = content.lower()
        if any(cue in lowered for cue in FACT_CUES):
            facts.append(content)
        if len(facts) >= 8:
            break
    return _dedupe(facts)


def _extract_vibes(rows: list[dict[str, str]], topic: str) -> list[str]:
    tokens = Counter()
    for row in rows:
        if row.get("role") == "user":
            tokens.update(_tokens(row.get("content", "")))
    matches = [word for word, _ in tokens.most_common(12) if word in VIBE_WORDS]
    if not matches:
        return []
    return [f"{topic}: recurring tone or theme around {', '.join(matches[:5])}"]


def _shorten(text: str, limit: int = 220) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\b[a-z0-9]{4,}\b", str(text).lower()))


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    unique = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
