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

import aiosqlite

from canonical_memory import search_canonical_direct_fact, search_relevant_canonical_memories, upsert_canonical_memory
from canonical_memory_inspector import inspect_canonical_memory
from canonical_memory_pin import set_canonical_memory_pin
from learning_pipeline import LearningPipeline
from lesson_store import init_lesson_db
from memory_control import forget_memory
from memory_links import add_memory_link
from memory_service import MemoryService
from storage import init_db
from voice_transcript_policy import clean_voice_transcript_for_intent


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-canonical-memory-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        learned = await LearningPipeline(db_path).handle("remember that my telegram test drink is teh ais", "telegram")
        _require(learned and "saved" in learned.lower(), "explicit memory was not saved")
        direct = await MemoryService(db_path).search_direct_fact("what is my telegram test drink")
        _require(direct == ["my telegram test drink is teh ais"], "canonical direct recall failed")
        canonical = await search_canonical_direct_fact(db_path, "my telegram test drink")
        _require(canonical == ["my telegram test drink is teh ais"], "canonical store did not return fact")
        _require(await _reinforcement_count(db_path, "telegram_test_drink") >= 2, "direct recall did not reinforce canonical memory")
        await LearningPipeline(db_path).handle("remember that my test snacks is ice cream for telegram voice", "telegram")
        repaired_query = clean_voice_transcript_for_intent("What is my test next for Telegram Voice?")
        repaired_direct = await MemoryService(db_path).search_direct_fact(repaired_query)
        _require(repaired_direct == ["my test snacks is ice cream for telegram voice"], "voice STT snack recall failed")
        plain_fact = clean_voice_transcript_for_intent("My Telegram test snack is bingsu.")
        plain_saved = await LearningPipeline(db_path).handle(plain_fact, "telegram")
        _require(plain_saved and "saved" in plain_saved.lower(), "direct voice test fact was not saved")
        name_query = clean_voice_transcript_for_intent("What is my Telegram test name?")
        name_direct = await MemoryService(db_path).search_direct_fact(name_query)
        normalized_name_direct = [item.lower().rstrip(".") for item in name_direct]
        _require("my telegram test snack is bingsu" in normalized_name_direct, "voice STT name/snack recall failed")
        forgotten = await forget_memory(db_path, "my telegram test drink")
        _require("canonical memory: 1" in forgotten, "forget did not mark canonical memory")
        after = await MemoryService(db_path).search_direct_fact("what is my telegram test drink")
        _require(after == [], "forgotten canonical memory leaked into recall")
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO preferences (key, value, source) VALUES ('city_pref', 'my telegram test city is Kyoto', 'telegram')"
            )
            await db.execute(
                """
                INSERT INTO lessons (raw_text, normalized_rule, lesson_type, scope, channel, confidence, status)
                VALUES ('prefer short replies', 'I prefer short Telegram replies', 'preference', 'global', 'telegram', 'high', 'active')
                """
            )
            await db.commit()
        from canonical_memory_migration import migrate_memory_to_canonical

        report = await migrate_memory_to_canonical(db_path)
        _require("Canonical memory migration:" in report, "migration report missing")
        _require("Preferences scanned:" in report, "migration preference count missing")
        _require("Lessons scanned:" in report, "migration lesson count missing")
        _require("Source rows linked:" in report, "migration source link count missing")
        first_links = await _count_links(db_path)
        _require(first_links >= 2, "migration did not link source rows")
        second_report = await migrate_memory_to_canonical(db_path)
        _require("Duplicate source links:" in second_report, "migration dedupe count missing")
        second_links = await _count_links(db_path)
        _require(second_links == first_links, "migration should not duplicate source links")
        await _seed_activation_rows(db_path)
        relevant = await search_relevant_canonical_memories(db_path, "project color", limit=1)
        _require(relevant == ["my active project color is green"], "activation scoring did not prefer reinforced recent memory")
        pinned = await set_canonical_memory_pin(db_path, "archive project color", pinned=True)
        _require("Pinned 1 canonical memory" in pinned, "pin command did not pin canonical memory")
        pinned_relevant = await search_relevant_canonical_memories(db_path, "unrelated query", limit=1)
        _require(pinned_relevant == ["my archive project color is blue"], "pinned memory was not eligible without overlap")
        unpinned = await set_canonical_memory_pin(db_path, "archive project color", pinned=False)
        _require("Unpinned 1 canonical memory" in unpinned, "unpin command did not unpin canonical memory")
        unpinned_relevant = await search_relevant_canonical_memories(db_path, "unrelated query", limit=1)
        _require(unpinned_relevant == [], "unpinned irrelevant memory should not activate")
        await _seed_association_rows(db_path)
        association_relevant = await search_relevant_canonical_memories(db_path, "sink repair", limit=2)
        _require(any("017-555" in item for item in association_relevant), "association neighbor did not join relevance recall")
        inspected = await inspect_canonical_memory(db_path, "active project color")
        _require("Canonical memory inspector:" in inspected, "canonical inspector header missing")
        _require("id: mem_" in inspected, "canonical inspector did not show memory ID")
        _require("class: active_saved_fact" in inspected, "canonical inspector did not show activation class")
        _require("subject: active_project_color" in inspected, "canonical inspector did not show subject key")
    print("canonical_memory_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _count_links(db_path: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        row = await (await db.execute("SELECT COUNT(*) FROM canonical_memory_sources")).fetchone()
    return int(row[0])


async def _reinforcement_count(db_path: str, subject_key: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        row = await (
            await db.execute("SELECT reinforcement_count FROM canonical_memory_items WHERE subject_key = ?", (subject_key,))
        ).fetchone()
    return int(row[0])


async def _seed_activation_rows(db_path: str) -> None:
    await upsert_canonical_memory(
        db_path,
        raw_text="my archive project color is blue",
        content="my archive project color is blue",
        kind="preference",
        scope="global",
        source_channel="telegram",
        confidence="high",
    )
    await upsert_canonical_memory(
        db_path,
        raw_text="my active project color is green",
        content="my active project color is green",
        kind="preference",
        scope="global",
        source_channel="telegram",
        confidence="high",
    )
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE canonical_memory_items
            SET updated_at = datetime('now', '-365 days'), reinforcement_count = 0
            WHERE subject_key = 'archive_project_color'
            """
        )
        await db.execute(
            "UPDATE canonical_memory_items SET reinforcement_count = 5 WHERE subject_key = 'active_project_color'"
        )
        await db.commit()


async def _seed_association_rows(db_path: str) -> None:
    await upsert_canonical_memory(
        db_path,
        raw_text="Ahmad fixed my sink",
        content="Ahmad fixed my sink",
        kind="profile_fact",
        scope="global",
        source_channel="smoke",
        confidence="high",
    )
    await upsert_canonical_memory(
        db_path,
        raw_text="Ahmad phone number is 017-555",
        content="Ahmad phone number is 017-555",
        kind="profile_fact",
        scope="global",
        source_channel="smoke",
        confidence="high",
    )
    async with aiosqlite.connect(db_path) as db:
        fixed = await (
            await db.execute("SELECT memory_id FROM canonical_memory_items WHERE content = 'Ahmad fixed my sink'")
        ).fetchone()
        phone = await (
            await db.execute("SELECT memory_id FROM canonical_memory_items WHERE content = 'Ahmad phone number is 017-555'")
        ).fetchone()
    _require(bool(fixed and phone), "association seed rows missing")
    ok = await add_memory_link(db_path, str(fixed[0]), str(phone[0]), relation="shared_entity", source_channel="smoke")
    _require(ok, "association link was not recorded")


if __name__ == "__main__":
    asyncio.run(main())
