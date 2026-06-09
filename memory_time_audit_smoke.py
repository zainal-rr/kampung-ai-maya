from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import aiosqlite

from canonical_memory import forget_canonical_memory, search_canonical_direct_fact, search_relevant_canonical_memories, upsert_canonical_memory
from memory_audit import record_memory_audit_event, recent_memory_audit_events
from memory_canaries import check_memory_canaries, seed_memory_canaries
from storage import init_db
from weekly_memory_live import live_weekly_canonical_distillation


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-memory-time-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await _canonical_audit_checks(db_path)
        await _weekly_audit_checks(db_path)
        await _canary_checks(db_path)
    print("memory_time_audit_smoke: ok")


async def _canonical_audit_checks(db_path: str) -> None:
    await upsert_canonical_memory(
        db_path,
        raw_text="remember that my memory audit drink is teh ais",
        content="my memory audit drink is teh ais",
        kind="preference",
        scope="global",
        source_channel="telegram",
        confidence="high",
    )
    await upsert_canonical_memory(
        db_path,
        raw_text="remember that my memory audit drink is kopi ais",
        content="my memory audit drink is kopi ais",
        kind="preference",
        scope="global",
        source_channel="telegram",
        confidence="high",
    )
    recalled = await search_canonical_direct_fact(db_path, "what is my memory audit drink")
    _require(recalled and "kopi ais" in recalled[0], "canonical recall failed")
    relevant = await search_relevant_canonical_memories(db_path, "memory audit drink")
    _require(relevant, "activation search failed")
    await forget_canonical_memory(db_path, "my memory audit drink")
    await record_memory_audit_event(
        db_path,
        event_type="canonical_write",
        subject_key="secret_probe",
        source_channel="smoke",
        content="my api key is sk-testtesttesttesttesttesttesttest",
    )
    events = await recent_memory_audit_events(db_path, limit=20)
    event_types = {event.event_type for event in events}
    for required in {"canonical_write", "canonical_update", "canonical_recall", "activation", "canonical_forget"}:
        _require(required in event_types, f"missing audit event {required}")
    secret = next(event for event in events if event.subject_key == "secret_probe")
    _require(secret.content_preview == "[redacted-sensitive]", "sensitive audit preview was not redacted")


async def _weekly_audit_checks(db_path: str) -> None:
    await seed_memory_canaries(db_path)

    async def distiller(_prompt: str) -> str:
        return (
            '{"facts":['
            '{"content":"Zainal prefers concise Telegram replies","kind":"preference","scope":"global","confidence":"high"},'
            '{"content":"my memory canary forgotten snack is hotteok","kind":"preference","scope":"global","confidence":"high"}'
            ']}'
        )

    async def reviewer(_prompt: str) -> str:
        return (
            '{"facts":['
            '{"content":"Zainal prefers concise Telegram replies","kind":"preference","scope":"global","confidence":"high"},'
            '{"content":"my memory canary forgotten snack is hotteok","kind":"preference","scope":"global","confidence":"high"}'
            '],"rejected":[],"confirmation_needed":[]}'
        )

    result = await live_weekly_canonical_distillation(
        db_path,
        run_key="2026-W99",
        data={"preferences": [], "lessons": []},
        distiller_agent=distiller,
        reviewer_agent=reviewer,
    )
    _require(result.saved == 1, "weekly should save only the durable non-forgotten fact")
    _require(result.rejected >= 1, "weekly should reject forgotten canary recreation")
    events = await recent_memory_audit_events(db_path, limit=40)
    event_types = {event.event_type for event in events}
    _require("weekly_candidate" in event_types, "weekly candidate audit missing")
    _require("weekly_save" in event_types, "weekly save audit missing")
    _require("weekly_reject" in event_types, "weekly reject audit missing")


async def _canary_checks(db_path: str) -> None:
    await seed_memory_canaries(db_path)
    active = await search_canonical_direct_fact(db_path, "what is my memory canary active color")
    _require(active and "azure" in active[0], "active canary recall failed")
    first = await check_memory_canaries(db_path)
    _require(first["passed"], f"canary baseline failed: {first['failures']}")
    async with aiosqlite.connect(db_path) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS session_summaries (id INTEGER PRIMARY KEY, summary TEXT)")
        await db.execute("INSERT INTO session_summaries (summary) VALUES (?)", ("forgotten snack is hotteok",))
        await db.commit()
    leaked = await check_memory_canaries(db_path)
    _require(not leaked["passed"], "forgotten canary leak was not detected")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
