from __future__ import annotations

import asyncio
import hashlib
import json
import math
from typing import Awaitable, Callable

import aiosqlite

EmbedCall = Callable[[list[str]], Awaitable[list[list[float]]]]

# Rerank only when lexical evidence is weak: a top lexical score below this
# (roughly two overlapping tokens) means the librarian is guessing. Exact
# matches never pay the embedding cost.
RERANK_CONFIDENCE = 20
# Cosine similarity contribution, scaled to lexical-score units.
COSINE_WEIGHT = 40
# Zero-evidence rows (no token/FTS/pin signal) may enter relevance context
# only when the embedder endorses them at least this strongly. They can
# never enter direct-fact recall. Tune against the live eval.
ZERO_EVIDENCE_MIN_COSINE = 0.55


async def init_vector_cache(db: aiosqlite.Connection) -> None:
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS canonical_memory_vectors (
            memory_id TEXT PRIMARY KEY,
            content_hash TEXT NOT NULL,
            model TEXT DEFAULT '',
            vector TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


async def rerank_with_embeddings(
    db_path: str,
    query: str,
    scored: list[tuple[int, str, str]],
    agent: EmbedCall | None,
    *,
    model: str = "",
) -> list[tuple[int, str, str]]:
    """Rerank (score, memory_id, content) candidates with cosine similarity.

    Contract:
    - rerank only; never adds or removes candidates (direct recall untouched)
    - gated: skipped when the top lexical score is already confident
    - cached: each memory is embedded once per content revision
    - fail-open: any provider error returns the lexical order unchanged
    """
    if agent is None or len(scored) < 2:
        return scored
    if scored and scored[0][0] >= RERANK_CONFIDENCE:
        return scored
    try:
        async with aiosqlite.connect(db_path) as db:
            await init_vector_cache(db)
            vectors = await _candidate_vectors(db, scored, agent, model)
            await db.commit()
        query_vector = (await agent([query]))[0]
    except Exception:
        return scored
    if not query_vector or not vectors:
        return scored
    reranked = []
    for score, memory_id, content in scored:
        vector = vectors.get(memory_id)
        cosine = _cosine(query_vector, vector) if vector else 0.0
        reranked.append((score + int(cosine * COSINE_WEIGHT), memory_id, content))
    reranked.sort(key=lambda item: item[0], reverse=True)
    return reranked


async def _candidate_vectors(
    db: aiosqlite.Connection,
    scored: list[tuple[int, str, str]],
    agent: EmbedCall,
    model: str,
) -> dict[str, list[float]]:
    vectors: dict[str, list[float]] = {}
    missing: list[tuple[str, str, str]] = []
    for _score, memory_id, content in scored:
        content_hash = _hash(content)
        cursor = await db.execute(
            "SELECT vector FROM canonical_memory_vectors WHERE memory_id = ? AND content_hash = ?",
            (memory_id, content_hash),
        )
        row = await cursor.fetchone()
        if row:
            vectors[memory_id] = json.loads(row[0])
        else:
            missing.append((memory_id, content_hash, content))
    if missing:
        embedded = await agent([content for _mid, _hash_, content in missing])
        for (memory_id, content_hash, _content), vector in zip(missing, embedded):
            vectors[memory_id] = vector
            await db.execute(
                """
                INSERT INTO canonical_memory_vectors (memory_id, content_hash, model, vector, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(memory_id) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    model = excluded.model,
                    vector = excluded.vector,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (memory_id, content_hash, model, json.dumps(vector)),
            )
    return vectors


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def _hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]


def embedding_rerank_enabled() -> bool:
    from maya_core.config import get_env

    return get_env("MEMORY_EMBED_RERANK_LIVE", "0") == "1" and bool(get_env("GOOGLE_API_KEY"))


def default_embedding_agent() -> EmbedCall | None:
    """Env-gated Gemini embeddings (MEMORY_EMBED_RERANK_LIVE=1 + GOOGLE_API_KEY).

    Multilingual on purpose: the eval's hard failure mode is cross-language
    Malay query -> English fact. Lazy imports keep no-key environments free
    of provider SDKs.
    """
    from maya_core.config import get_env

    if not embedding_rerank_enabled():
        return None
    api_key = get_env("GOOGLE_API_KEY")
    model = get_env("GEMINI_EMBED_MODEL", "gemini-embedding-001")

    async def _embed(texts: list[str]) -> list[list[float]]:
        from google import genai

        def _call() -> list[list[float]]:
            client = genai.Client(api_key=api_key)
            result = client.models.embed_content(model=model, contents=texts)
            return [list(item.values) for item in result.embeddings]

        return await asyncio.to_thread(_call)

    return _embed


def default_embedding_model_name() -> str:
    from maya_core.config import get_env

    return get_env("GEMINI_EMBED_MODEL", "gemini-embedding-001")
