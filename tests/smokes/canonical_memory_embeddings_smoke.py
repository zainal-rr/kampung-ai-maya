from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import tempfile
from pathlib import Path

from maya_memory.canonical_memory import search_relevant_canonical_memories, upsert_canonical_memory
from canonical_memory_embeddings import RERANK_CONFIDENCE, rerank_with_embeddings
from lesson_store import init_lesson_db
from storage import init_db

# Fake semantic space: "snack food munch kuih" cluster vs "wifi network" cluster.
VECTORS = {
    "my favourite snack is kuih lapis": [1.0, 0.1, 0.0],
    "my home wifi network name is KampungNet": [0.0, 0.1, 1.0],
    "what food do I like to munch on": [0.95, 0.2, 0.05],
}


def fake_embedder(calls: list[list[str]]):
    async def _embed(texts: list[str]) -> list[list[float]]:
        calls.append(texts)
        return [VECTORS.get(text, [0.0, 1.0, 0.0]) for text in texts]

    return _embed


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-embed-rerank-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        for content in ("my favourite snack is kuih lapis", "my home wifi network name is KampungNet"):
            await upsert_canonical_memory(
                db_path, raw_text=content, content=content, kind="preference",
                scope="global", source_channel="smoke", confidence="high",
            )

        # 1) Paraphrase query: lexical scoring alone cannot rank the snack
        # fact first; the fake embedder can. ("food"/"munch" share no tokens
        # with the stored fact, both candidates enter via weak evidence.)
        calls: list[list[str]] = []
        query = "what food do I like to munch on"
        candidates = [
            (8, "mem_a", "my home wifi network name is KampungNet"),
            (8, "mem_b", "my favourite snack is kuih lapis"),
        ]
        reranked = await rerank_with_embeddings(db_path, query, candidates, fake_embedder(calls))
        _require(reranked[0][2] == "my favourite snack is kuih lapis", f"rerank failed: {reranked}")
        _require(len(reranked) == len(candidates), "rerank must not add or drop candidates")

        # 2) Cache: second call embeds only the query, not the memories.
        calls2: list[list[str]] = []
        await rerank_with_embeddings(db_path, query, candidates, fake_embedder(calls2))
        embedded_texts = [text for batch in calls2 for text in batch]
        _require(embedded_texts == [query], f"cache miss on second call: {embedded_texts}")

        # 3) Gating: confident lexical top hit skips the embedder entirely.
        calls3: list[list[str]] = []
        confident = [(RERANK_CONFIDENCE + 5, "mem_b", "my favourite snack is kuih lapis"), (2, "mem_a", "other")]
        result = await rerank_with_embeddings(db_path, "favourite snack", confident, fake_embedder(calls3))
        _require(result == confident and not calls3, "confident lexical result should skip embedding")

        # 4) Fail-open: crashing embedder returns lexical order unchanged.
        async def crashing(_texts: list[str]) -> list[list[float]]:
            raise RuntimeError("provider down")

        result = await rerank_with_embeddings(db_path, query, candidates, crashing)
        _require(result == candidates, "embedder failure must fall back to lexical order")

        # 5) End to end: injected agent flows through the search path.
        calls5: list[list[str]] = []
        results = await search_relevant_canonical_memories(
            db_path, query, limit=2, embedding_agent=fake_embedder(calls5)
        )
        _require(bool(results), "search returned nothing")
        _require(results[0] == "my favourite snack is kuih lapis", f"end-to-end rerank failed: {results}")

        # 6) No agent: behavior identical to lexical-only (no env flag set).
        plain = await search_relevant_canonical_memories(db_path, "what is my favourite snack", limit=2)
        _require(plain and "kuih lapis" in plain[0], "lexical-only path broken")
    print("canonical_memory_embeddings_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
