from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


"""Deterministic smoke for nightly consolidation. No providers, temp DB only.

Proves the five contracts:
1. Facts approved by the reviewer are saved with nightly source attribution.
2. A fact whose subject was forgotten is rejected, never resurrected.
3. Links are recorded only between active canonical memories, and
   spreading activation surfaces a neighbor without leaking forgotten rows.
4. The decay report lists stale unused memories but mutates nothing.
5. A second run with no new episodes is a zero-delta skip: 0 provider calls.
"""

import asyncio
import tempfile
from pathlib import Path

import aiosqlite

from maya_memory.canonical_memory import forget_canonical_memory, upsert_canonical_memory
from maya_memory.memory_links import expand_with_neighbors
from maya_core.nightly_consolidation import run_nightly_consolidation

FAKE_DISTILLER_REPLY = """
{
  "facts": [
    {"content": "my barber is samad", "kind": "profile_fact", "scope": "global", "confidence": "high"},
    {"content": "my favourite snack is hotteok", "kind": "preference", "scope": "global", "confidence": "high"}
  ],
  "links": [
    {"source": "my barber is samad", "target": "my plumber is ahmad", "relation": "shared_entity"},
    {"source": "my barber is samad", "target": "my favourite snack is hotteok", "relation": "same_episode"}
  ]
}
"""

FAKE_REVIEW_REPLY = """
{
  "facts": [
    {"content": "my barber is samad", "kind": "profile_fact", "scope": "global", "confidence": "high"},
    {"content": "my favourite snack is hotteok", "kind": "preference", "scope": "global", "confidence": "high"}
  ],
  "rejected": [],
  "confirmation_needed": []
}
"""


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-nightly-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _seed(db_path)
        calls = {"distiller": 0, "reviewer": 0}

        async def fake_distiller(prompt: str) -> str:
            calls["distiller"] += 1
            _require(
                "Episodes:" in prompt and ("barber" in prompt or "tailor" in prompt),
                "episodes were not replayed to the distiller",
            )
            return FAKE_DISTILLER_REPLY

        async def fake_reviewer(prompt: str) -> str:
            calls["reviewer"] += 1
            return FAKE_REVIEW_REPLY

        first = await run_nightly_consolidation(
            db_path, distiller_agent=fake_distiller, reviewer_agent=fake_reviewer, run_key="night-test-1"
        )
        _require(not first.skipped, "first run should not skip")
        _require(first.provider_calls == 2, f"expected 2 provider calls, got {first.provider_calls}")
        _require(first.saved == 1, f"expected 1 saved fact (hotteok blocked), got {first.saved}")
        _require(first.rejected >= 1, "forgotten-subject fact was not rejected")
        _require(await _status(db_path, "favourite_snack") == "forgotten", "forgotten fact was resurrected")
        _require(await _status(db_path, "barber") == "active", "new fact was not saved as active")

        _require(first.links_recorded == 1, f"expected 1 link (forgotten endpoint dropped), got {first.links_recorded}")
        _require(first.links_dropped == 1, "link to forgotten memory should have been dropped")
        barber_id = await _memory_id(db_path, "barber")
        neighbors = await expand_with_neighbors(db_path, [barber_id])
        _require(any("ahmad" in content for _mid, content in neighbors), "spreading activation missed the plumber")
        _require(all("hotteok" not in content for _mid, content in neighbors), "forgotten memory leaked through links")

        _require(any("kuantan" in item for item in first.decay_candidates), "stale memory missing from decay report")
        _require(await _status(db_path, "old_office") == "active", "decay report must not mutate memories")

        second = await run_nightly_consolidation(
            db_path, distiller_agent=fake_distiller, reviewer_agent=fake_reviewer, run_key="night-test-2"
        )
        _require(second.skipped and second.provider_calls == 0, "zero-delta run must skip with no provider calls")
        _require(calls["distiller"] == 1 and calls["reviewer"] == 1, "providers were called on a zero-delta night")

        await _insert_history(db_path, "user", "my password is hunter2 and should not be saved", "2026-06-10 10:00:00")
        sensitive_only = await run_nightly_consolidation(
            db_path, distiller_agent=fake_distiller, reviewer_agent=fake_reviewer, run_key="night-test-3"
        )
        _require(sensitive_only.skipped and sensitive_only.provider_calls == 0, "sensitive-only night should skip providers")
        _require(await _latest_watermark(db_path) == "2026-06-10 10:00:00", "sensitive-only night did not advance watermark")

        await _insert_history(db_path, "user", "my tailor is mariam", "2026-06-11 10:00:00")
        missing_reviewer = await run_nightly_consolidation(
            db_path, distiller_agent=fake_distiller, reviewer_agent=None, run_key="night-test-4"
        )
        _require(missing_reviewer.skipped, "missing reviewer should skip by default")
        _require(missing_reviewer.skip_reason == "reviewer required but not configured", "missing reviewer skip reason wrong")
        _require(calls["distiller"] == 1 and calls["reviewer"] == 1, "distiller ran without reviewer")

        async def failing_reviewer(prompt: str) -> str:
            calls["reviewer"] += 1
            raise RuntimeError("review unavailable")

        failed_review = await run_nightly_consolidation(
            db_path, distiller_agent=fake_distiller, reviewer_agent=failing_reviewer, run_key="night-test-5"
        )
        _require(failed_review.provider_calls == 2, "review-failure run should record both attempted provider calls")
        _require(failed_review.saved == 0, "review failure must save zero canonical facts")
        _require(failed_review.links_recorded == 0, "review failure must not record unreviewed links")

        audit = await _audit_channels(db_path)
        _require("nightly_consolidation" in audit, "audit events missing nightly source channel")

    print("PASS nightly_consolidation_smoke: save, no-resurrect, links, decay report, zero-delta skip, audit")


async def _seed(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS history (
                user_id INTEGER, role TEXT, content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            "INSERT INTO history (user_id, role, content, timestamp) VALUES (1, 'user', 'my barber is samad, his shop is next to ahmad the plumber', '2026-06-09 09:00:00')"
        )
        await db.execute(
            "INSERT INTO history (user_id, role, content, timestamp) VALUES (1, 'assistant', 'Noted about samad the barber.', '2026-06-09 09:00:05')"
        )
        await db.commit()
    await upsert_canonical_memory(
        db_path, raw_text="my plumber is ahmad", content="my plumber is ahmad",
        kind="profile_fact", scope="global", source_channel="smoke", confidence="high",
    )
    await upsert_canonical_memory(
        db_path, raw_text="my favourite snack is hotteok", content="my favourite snack is hotteok",
        kind="preference", scope="global", source_channel="smoke", confidence="high",
    )
    await forget_canonical_memory(db_path, "my favourite snack is hotteok")
    await upsert_canonical_memory(
        db_path, raw_text="my old office is in kuantan", content="my old office is in kuantan",
        kind="profile_fact", scope="global", source_channel="smoke", confidence="medium",
    )
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE canonical_memory_items SET updated_at = '2026-01-01 00:00:00', last_used_at = NULL WHERE subject_key LIKE '%old_office%' OR subject_key LIKE '%kuantan%'"
        )
        await db.commit()


async def _insert_history(db_path: str, role: str, content: str, timestamp: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO history (user_id, role, content, timestamp) VALUES (1, ?, ?, ?)",
            (role, content, timestamp),
        )
        await db.commit()


async def _status(db_path: str, subject_fragment: str) -> str:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT status FROM canonical_memory_items WHERE subject_key LIKE ? ORDER BY updated_at DESC LIMIT 1",
            (f"%{subject_fragment}%",),
        )
        row = await cursor.fetchone()
    return str(row[0]) if row else ""


async def _memory_id(db_path: str, subject_fragment: str) -> str:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT memory_id FROM canonical_memory_items WHERE subject_key LIKE ? AND status = 'active' LIMIT 1",
            (f"%{subject_fragment}%",),
        )
        row = await cursor.fetchone()
    return str(row[0]) if row else ""


async def _audit_channels(db_path: str) -> set[str]:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT DISTINCT source_channel FROM memory_audit_events")
        return {str(row[0]) for row in await cursor.fetchall()}


async def _latest_watermark(db_path: str) -> str:
    async with aiosqlite.connect(db_path) as db:
        row = await (
            await db.execute("SELECT watermark FROM nightly_consolidation_runs ORDER BY id DESC LIMIT 1")
        ).fetchone()
    return str(row[0]) if row else ""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
