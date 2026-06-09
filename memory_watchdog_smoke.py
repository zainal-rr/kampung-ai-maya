from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import aiosqlite

from canonical_memory import search_relevant_canonical_memories, upsert_canonical_memory
from lesson_store import init_lesson_db
from memory_watchdog import format_watchdog_report, run_memory_watchdog
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-memory-watchdog-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        await upsert_canonical_memory(
            db_path,
            raw_text="my watchdog drink is kopi o",
            content="my watchdog drink is kopi o",
            kind="preference",
            scope="global",
            source_channel="smoke",
            confidence="high",
        )
        recalled = await search_relevant_canonical_memories(db_path, "watchdog drink", limit=3)
        _require(bool(recalled), "seeded fact was not recallable")

        # First run: seeds canaries (reported as an issue once), audit is live.
        report = await run_memory_watchdog(db_path)
        _require(any("canaries were not seeded" in issue for issue in report["issues"]), "first run should report canary seeding")
        _require(len(report["canaries"]) >= 5, "canary checks did not run")

        # Second run: canaries seeded, recall happened, audit recorded: pass.
        report = await run_memory_watchdog(db_path)
        _require(report["passed"], f"healthy db should pass, got issues: {report['issues']}")
        _require(report["stats"]["recall_recent"], "recall_recent not detected")
        _require(report["stats"]["audit_recent"], "audit_recent not detected")

        # Simulate the production failure: recalls happen, audit stays silent.
        async with aiosqlite.connect(db_path) as db:
            await db.execute("DELETE FROM memory_audit_events")
            await db.execute(
                "UPDATE canonical_memory_items SET last_used_at = CURRENT_TIMESTAMP WHERE subject_key = 'watchdog_drink'"
            )
            await db.commit()
        report = await run_memory_watchdog(db_path)
        _require(not report["passed"], "silent audit should trigger an alert")
        _require(any("audit silent" in issue for issue in report["issues"]), "silent audit was not detected")
        text = format_watchdog_report(report)
        _require("Memory watchdog:" in text and "Status:" in text, "report format broken")
    print("memory_watchdog_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
