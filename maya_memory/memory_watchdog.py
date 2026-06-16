from __future__ import annotations

import argparse
import asyncio

import aiosqlite

from curated_memory import CORE_SCOPE, PROFILE_SCOPE
from memory_canaries import check_memory_canaries, seed_memory_canaries

AUDIT_SILENCE_HOURS = 24


async def run_memory_watchdog(db_path: str) -> dict[str, object]:
    """Production liveness checks for the memory subsystem.

    Catches the failure mode found in review: recalls happening (reinforcement
    rising, last_used_at fresh) while the audit table stays silent, meaning
    the governance layer everyone trusts is not actually recording.
    """
    issues: list[str] = []
    # Sample stats before canary checks: canary seeding/checking writes audit
    # events itself, which would mask the very audit silence we test for.
    stats = await _stats(db_path)
    await _ensure_canaries(db_path, issues)
    canaries = await check_memory_canaries(db_path)
    for failure in canaries["failures"]:
        issues.append(f"canary {failure['canary_id']}: {failure['failure_reason']}")
    if stats["recall_recent"] and not stats["audit_recent"]:
        issues.append(
            "audit silent: canonical memory was recalled in the last "
            f"{AUDIT_SILENCE_HOURS}h but no audit events were recorded; "
            "the running bot is likely on stale code or audit writes are failing"
        )
    if stats["expired_active"]:
        issues.append(f"{stats['expired_active']} active rows past expires_at (search hides them; cleanup never ran)")
    return {"passed": not issues, "issues": issues, "stats": stats, "canaries": canaries["results"]}


async def memory_watchdog_text(db_path: str) -> str:
    return format_watchdog_report(await run_memory_watchdog(db_path))


def format_watchdog_report(report: dict[str, object]) -> str:
    stats = report["stats"]
    lines = [
        "Memory watchdog:",
        f"1) Status: {'pass' if report['passed'] else 'ALERT'}",
        f"2) Active canonical memories: {stats['active']} ({stats['temporary_active']} temporary/test)",
        f"3) Recall in last {AUDIT_SILENCE_HOURS}h: {'yes' if stats['recall_recent'] else 'no'}; "
        f"audit events in last {AUDIT_SILENCE_HOURS}h: {'yes' if stats['audit_recent'] else 'no'}",
        f"4) Canaries checked: {len(report['canaries'])}",
        f"5) Stale curated rows: {stats['stale_curated']}",
    ]
    if report["issues"]:
        lines.append("6) Issues:")
        lines.extend(f"   - {issue}" for issue in report["issues"])
    return "\n".join(lines)


async def _ensure_canaries(db_path: str, issues: list[str]) -> None:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'memory_canaries'"
        )
        exists = bool(await cursor.fetchone())
        seeded = False
        if exists:
            count = await (await db.execute("SELECT count(*) FROM memory_canaries")).fetchone()
            seeded = bool(count and count[0])
    if not seeded:
        await seed_memory_canaries(db_path)
        issues.append("canaries were not seeded; seeded them now (leak detection was inactive until this run)")


async def _stats(db_path: str) -> dict[str, object]:
    window = f"-{AUDIT_SILENCE_HOURS} hours"
    async with aiosqlite.connect(db_path) as db:
        active = await _one(db, "SELECT count(*) FROM canonical_memory_items WHERE status = 'active'")
        temporary_active = await _one(
            db,
            "SELECT count(*) FROM canonical_memory_items WHERE status = 'active' AND (temporary = 1 OR test_marker = 1)",
        )
        expired_active = await _one(
            db,
            "SELECT count(*) FROM canonical_memory_items WHERE status = 'active' AND expires_at IS NOT NULL AND expires_at <= datetime('now')",
        )
        recall_recent = bool(
            await _one(
                db,
                "SELECT count(*) FROM canonical_memory_items WHERE last_used_at >= datetime('now', ?)",
                (window,),
            )
        )
        audit_recent = bool(
            await _one(
                db,
                "SELECT count(*) FROM memory_audit_events WHERE created_at >= datetime('now', ?)",
                (window,),
            )
        )
        stale_curated = await _one(
            db,
            "SELECT count(*) FROM curated_memory_items WHERE scope IN (?, ?) AND status = 'stale'",
            (CORE_SCOPE, PROFILE_SCOPE),
        )
    return {
        "active": active,
        "temporary_active": temporary_active,
        "expired_active": expired_active,
        "recall_recent": recall_recent,
        "audit_recent": audit_recent,
        "stale_curated": stale_curated,
    }


async def _one(db: aiosqlite.Connection, query: str, params: tuple = ()) -> int:
    try:
        row = await (await db.execute(query, params)).fetchone()
    except aiosqlite.OperationalError:
        return 0
    return int(row[0]) if row and row[0] is not None else 0


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Run the memory watchdog. Exit 1 on alert.")
    parser.add_argument("--db", default="session_history.db", help="SQLite database path.")
    args = parser.parse_args()
    report = await run_memory_watchdog(args.db)
    print(format_watchdog_report(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
