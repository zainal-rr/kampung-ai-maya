"""W2-B paraphrase recall canaries.

R4/R5 prove that semantic direct recall can surface an active paraphrase
candidate, while superseded/forgotten rows stay out of the vector pool.
"""

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

from maya_core.lesson_store import init_lesson_db
from maya_core.storage import init_db
from maya_memory.canonical_memory import (
    forget_canonical_memory,
    search_canonical_direct_fact,
    upsert_canonical_memory,
)

VECTORS = {
    "my preferred airline is AirAsia": [1.0, 0.0, 0.0],
    "my preferred airline is Malaysia Airlines": [1.0, 0.0, 0.0],
    "my preferred hotel chain is Marriott": [0.0, 1.0, 0.0],
    "my favourite colour is purple": [0.0, 0.0, 1.0],
    "which carrier do I prefer": [0.98, 0.02, 0.0],
    "which colour shade do I like": [0.0, 0.0, 0.99],
}


def fake_embedder(calls: list[list[str]]):
    async def _embed(texts: list[str]) -> list[list[float]]:
        calls.append(texts)
        return [VECTORS.get(text, [0.0, 0.01, 0.0]) for text in texts]

    return _embed


async def _save(db_path: str, content: str) -> None:
    await upsert_canonical_memory(
        db_path,
        raw_text=content,
        content=content,
        kind="preference",
        scope="global",
        source_channel="w2b_canary",
        confidence="high",
    )


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-w2b-") as tmp:
        db_path = str(Path(tmp) / "memory.db")
        await init_db(db_path)
        await init_lesson_db(db_path)

        # R4: active semantic paraphrase can surface the current canonical fact.
        await _save(db_path, "my preferred airline is AirAsia")
        await _save(db_path, "my preferred hotel chain is Marriott")
        calls: list[list[str]] = []
        recalled = await search_canonical_direct_fact(
            db_path,
            "which carrier do I prefer",
            embedding_agent=fake_embedder(calls),
        )
        _require(recalled == ["my preferred airline is AirAsia"], f"R4 failed: {recalled}")

        # R5: superseded rows are not in the vector pool, even if semantically
        # tempting; the current active row is the only airline candidate.
        await _save(db_path, "my preferred airline is Malaysia Airlines")
        await _save(db_path, "my preferred airline is AirAsia")
        calls = []
        recalled = await search_canonical_direct_fact(
            db_path,
            "which carrier do I prefer",
            embedding_agent=fake_embedder(calls),
        )
        _require(recalled == ["my preferred airline is AirAsia"], f"R5 current value failed: {recalled}")
        embedded_texts = [text for batch in calls for text in batch]
        _require("my preferred airline is Malaysia Airlines" not in embedded_texts,
                 f"R5 superseded row reached embedder: {embedded_texts}")

        # Forgotten rows are also filtered before vector scoring.
        await _save(db_path, "my favourite colour is purple")
        await forget_canonical_memory(db_path, "my favourite colour")
        calls = []
        recalled = await search_canonical_direct_fact(
            db_path,
            "which colour shade do I like",
            embedding_agent=fake_embedder(calls),
        )
        _require(recalled in ([], None), f"forgotten semantic row leaked: {recalled}")
        embedded_texts = [text for batch in calls for text in batch]
        _require("my favourite colour is purple" not in embedded_texts,
                 f"forgotten row reached embedder: {embedded_texts}")

    print("memory_paraphrase_canaries_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
