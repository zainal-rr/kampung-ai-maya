from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


"""Guards for the association layer. Each test maps to a named invariant:

I1 temporary_link_refused   - add_memory_link refuses temporary/test endpoints
I2 temporary_never_expands  - even a force-inserted link to a temporary row
                              never surfaces through expand_with_neighbors
I3 no_displacement          - association neighbors never push a lexical hit
                              out of the top-`limit` relevance context
I4 dedup_token              - a rephrasing of an existing fact is detected
                              and NOT inserted by the nightly save gate
I5 dedup_embedding          - anchored embedding catches a cross-phrasing
                              duplicate that token containment misses
I6 dedup_no_false_positive  - a genuinely new fact is not flagged duplicate
I7 dedup_update_not_dropped - a changed value on a known subject (numeric or
                              disjoint value) is an UPDATE, never a duplicate;
                              suppressing it would reinforce a stale fact
"""

import asyncio
import tempfile
from pathlib import Path

import aiosqlite

from maya_memory.canonical_memory import search_relevant_canonical_memories, upsert_canonical_memory
from maya_memory.canonical_memory_dedup import find_semantic_duplicate
from lesson_store import init_lesson_db
from memory_links import add_memory_link, expand_with_neighbors
from storage import init_db


async def _seed(db_path: str, content: str, **kwargs) -> str:
    return await upsert_canonical_memory(
        db_path, raw_text=content, content=content, kind=kwargs.get("kind", "preference"),
        scope=kwargs.get("scope", "global"), source_channel="links_smoke", confidence="high",
    )


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-memory-links-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_lesson_db(db_path)

        durable_a = await _seed(db_path, "my badminton night is Friday")
        durable_b = await _seed(db_path, "my badminton kaki is Farid")
        temp_row = await _seed(db_path, "my telegram test drink is teh ais")  # word 'test' -> temporary

        # I1: linking to a temporary row is refused in both directions.
        _require(not await add_memory_link(db_path, durable_a, temp_row), "I1: link TO temporary row was created")
        _require(not await add_memory_link(db_path, temp_row, durable_a), "I1: link FROM temporary row was created")
        _require(await add_memory_link(db_path, durable_a, durable_b), "I1: durable-durable link refused")

        # I2: even a force-inserted (raw SQL) link to a temporary row never
        # surfaces through expansion -- read-time guard, not just write-time.
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT INTO memory_links (source_memory_id, target_memory_id, relation) VALUES (?, ?, 'related')",
                (durable_a, temp_row),
            )
            await db.commit()
        neighbors = await expand_with_neighbors(db_path, [durable_a])
        neighbor_contents = [content for _mid, content in neighbors]
        _require(all("teh ais" not in content for content in neighbor_contents),
                 f"I2: temporary row leaked through forced link: {neighbor_contents}")
        _require(any("Farid" in content for content in neighbor_contents),
                 f"I2: legitimate neighbor missing: {neighbor_contents}")

        # I3: three strong lexical hits + a linked neighbor; the neighbor must
        # not displace any of them from the top-3 context.
        hit1 = await _seed(db_path, "my durian supplier in Bandar is Pak Long")
        await _seed(db_path, "my durian budget is 40 dollars monthly")
        await _seed(db_path, "my durian season reminder is June")
        unrelated = await _seed(db_path, "my plumber name is Rahman")
        _require(await add_memory_link(db_path, hit1, unrelated), "I3 setup: link refused")
        results = await search_relevant_canonical_memories(db_path, "durian supplier budget season", limit=3)
        _require(len(results) == 3, f"I3: expected 3 results, got {len(results)}")
        _require(all("durian" in item for item in results),
                 f"I3: neighbor displaced a lexical hit from top-3: {results}")
        wide = await search_relevant_canonical_memories(db_path, "durian supplier budget season", limit=5)
        _require(any("Rahman" in item for item in wide),
                 f"I3: neighbor should still fill spare slots at limit=5: {wide}")

        # I4: rephrasing of an existing fact is a confident token duplicate.
        await _seed(db_path, "Zainal reply style is short and direct with no exclamation marks")
        duplicate = await find_semantic_duplicate(
            db_path, "Zainal reply style is short and direct, no exclamation marks"
        )
        _require(duplicate is not None and duplicate[1] == "token_containment",
                 f"I4: rephrasing not detected as duplicate: {duplicate}")

        # I5: token containment deliberately misses this cross-phrasing, but
        # an anchored embedding match should catch it.
        embedded = await find_semantic_duplicate(
            db_path,
            "Zainal reply style is brief, no enthusiastic punctuation",
            embed_agent=_fake_embed,
        )
        _require(embedded is not None and embedded[1] == "embedding_cosine",
                 f"I5: anchored embedding duplicate not detected: {embedded}")

        # I6: a genuinely new fact is not a duplicate.
        fresh = await find_semantic_duplicate(db_path, "my dentist appointment is in August at Klinik Pergigian")
        _require(fresh is None, f"I6: new fact wrongly flagged duplicate: {fresh}")

        # I7: changed values are updates, never duplicates -- even when the
        # embedder thinks the sentences are identical (same_vec = cosine 1.0).
        await _seed(db_path, "my lunch budget is 15 dollars")
        updated_number = await find_semantic_duplicate(
            db_path, "Zainal lunch budget is 20 dollars", embed_agent=_same_vec
        )
        _require(updated_number is None,
                 f"I7: numeric value update suppressed as duplicate: {updated_number}")
        await _seed(db_path, "my gym day is Tuesday")
        updated_value = await find_semantic_duplicate(
            db_path, "my gym day is Wednesday", embed_agent=_same_vec
        )
        _require(updated_value is None,
                 f"I7: disjoint value update suppressed as duplicate: {updated_value}")

    print("memory_links_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _same_vec(texts: list[str]) -> list[list[float]]:
    # Worst case for update suppression: embedder sees all texts as identical.
    return [[1.0, 0.0] for _ in texts]


async def _fake_embed(texts: list[str]) -> list[list[float]]:
    vectors = []
    for text in texts:
        lowered = text.lower()
        if "reply style" in lowered or "short and direct" in lowered:
            vectors.append([1.0, 0.0, 0.0])
        else:
            vectors.append([0.0, 1.0, 0.0])
    return vectors


if __name__ == "__main__":
    asyncio.run(main())
