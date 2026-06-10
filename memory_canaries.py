from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import aiosqlite

from canonical_memory import forget_canonical_memory, subject_key_from_text, upsert_canonical_memory
from memory_audit import hash_content, record_memory_audit_event


@dataclass(frozen=True)
class CanarySpec:
    canary_id: str
    content: str
    expected_state: str
    kind: str = "preference"
    scope: str = "global"
    pinned: bool = False

    @property
    def subject_key(self) -> str:
        return subject_key_from_text(self.content)

    @property
    def value(self) -> str:
        return self.content.split(" is ", 1)[-1]


CANARIES = (
    CanarySpec("active_memory_canary", "my memory canary active color is azure", "active"),
    CanarySpec("forgotten_memory_canary", "my memory canary forgotten snack is hotteok", "forgotten"),
    CanarySpec("temporary_memory_canary", "my memory canary temporary test fruit is rambutan", "temporary_expired"),
    CanarySpec("project_memory_canary", "kampung ai project canary status is active", "project_active", kind="project_fact", scope="project:kampung-ai"),
    CanarySpec("pinned_memory_canary", "maya pinned canary rule is protect forgotten memories", "active", kind="lesson", pinned=True),
)


async def init_memory_canary_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_canaries (
                canary_id TEXT PRIMARY KEY,
                subject_key TEXT NOT NULL,
                expected_state TEXT NOT NULL,
                value_hash TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                forgotten_at DATETIME,
                expires_at DATETIME,
                last_checked_at DATETIME,
                last_result TEXT DEFAULT '',
                failure_reason TEXT DEFAULT ''
            )
            """
        )
        await db.commit()


async def seed_memory_canaries(db_path: str) -> None:
    await init_memory_canary_db(db_path)
    for spec in CANARIES:
        memory_id = await upsert_canonical_memory(
            db_path,
            raw_text=spec.content,
            content=spec.content,
            kind=spec.kind,
            scope=spec.scope,
            source_channel="memory_canary",
            source_ref=spec.canary_id,
            confidence="high",
            pinned=spec.pinned,
        )
        forgotten_at = ""
        expires_at = ""
        if spec.expected_state == "forgotten":
            await forget_canonical_memory(db_path, spec.content)
            forgotten_at = _now()
        if spec.expected_state == "temporary_expired":
            expires_at = _past()
            await _expire_canary(db_path, memory_id, expires_at)
        await _upsert_canary_row(db_path, spec, forgotten_at=forgotten_at, expires_at=expires_at)


async def check_memory_canaries(db_path: str) -> dict[str, object]:
    await init_memory_canary_db(db_path)
    rows = await _canary_rows(db_path)
    results = []
    for row in rows:
        spec = _spec_for(str(row["canary_id"]))
        if not spec:
            continue
        result, reason = await _check_one(db_path, spec)
        await _record_check(db_path, spec, result, reason)
        results.append({"canary_id": spec.canary_id, "result": result, "failure_reason": reason})
        await record_memory_audit_event(
            db_path,
            event_type="leak_check",
            memory_id=spec.canary_id,
            subject_key=spec.subject_key,
            status_before=str(row["last_result"] or ""),
            status_after=result,
            source_channel="memory_canary",
            source_ref=reason,
            content=spec.content,
        )
    failures = [item for item in results if item["result"] != "pass"]
    return {"passed": not failures, "results": results, "failures": failures}


async def format_memory_leak_report(db_path: str) -> str:
    await init_memory_canary_db(db_path)
    rows = await _canary_rows(db_path)
    if not rows:
        return "Memory leak canaries:\n1) Not seeded yet."
    lines = ["Memory leak canaries:"]
    for index, row in enumerate(rows, start=1):
        result = row["last_result"] or "not_checked"
        reason = f" | {row['failure_reason']}" if row["failure_reason"] else ""
        lines.append(f"{index}) {row['canary_id']}: {result}{reason}")
    return "\n".join(lines)


async def _check_one(db_path: str, spec: CanarySpec) -> tuple[str, str]:
    canonical = await _canonical_rows(db_path, spec.subject_key)
    active = [row for row in canonical if row["status"] == "active"]
    if spec.expected_state in {"active", "project_active"}:
        return ("pass", "") if active else ("fail", "expected active canonical canary")
    if spec.expected_state == "forgotten":
        if active:
            return "fail", "forgotten canary is active in canonical memory"
        leak = await _derived_leak(db_path, spec.value)
        return ("fail", leak) if leak else ("pass", "")
    if spec.expected_state == "temporary_expired":
        durable = [row for row in active if not row["temporary"] and not row["test_marker"]]
        if durable:
            return "fail", "temporary canary became durable canonical memory"
        leak = await _derived_leak(db_path, spec.value)
        return ("fail", leak) if leak else ("pass", "")
    return "fail", f"unknown expected state {spec.expected_state}"


async def _derived_leak(db_path: str, value: str) -> str:
    needle = value.lower()
    checks = {
        "preferences": ("key || ' ' || value", ""),
        "lessons": ("raw_text || ' ' || normalized_rule", ""),
        "history": ("content", ""),
        "session_search": ("content", ""),
        "session_summaries": ("summary", ""),
        "weekly_summaries": ("summary", ""),
        "curated_memory_items": ("content", "status = 'active'"),
    }
    async with aiosqlite.connect(db_path) as db:
        for table, (expr, extra_where) in checks.items():
            if not await _table_exists(db, table):
                continue
            where = f"{extra_where} AND " if extra_where else ""
            try:
                cursor = await db.execute(
                    f"SELECT 1 FROM {table} WHERE {where}lower({expr}) LIKE ? LIMIT 1",
                    (f"%{needle}%",),
                )
            except aiosqlite.OperationalError:
                continue
            if await cursor.fetchone():
                return f"forgotten/temporary value leaked through {table}"
    return ""


async def _upsert_canary_row(db_path: str, spec: CanarySpec, *, forgotten_at: str, expires_at: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO memory_canaries (canary_id, subject_key, expected_state, value_hash, forgotten_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(canary_id) DO UPDATE SET
                subject_key = excluded.subject_key,
                expected_state = excluded.expected_state,
                value_hash = excluded.value_hash,
                forgotten_at = COALESCE(excluded.forgotten_at, forgotten_at),
                expires_at = COALESCE(excluded.expires_at, expires_at)
            """,
            (spec.canary_id, spec.subject_key, spec.expected_state, hash_content(spec.value), forgotten_at or None, expires_at or None),
        )
        await db.commit()


async def _expire_canary(db_path: str, memory_id: str, expires_at: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE canonical_memory_items SET status = 'expired', expires_at = ?, updated_at = CURRENT_TIMESTAMP WHERE memory_id = ?",
            (expires_at, memory_id),
        )
        await db.commit()


async def _record_check(db_path: str, spec: CanarySpec, result: str, reason: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE memory_canaries
            SET last_checked_at = CURRENT_TIMESTAMP, last_result = ?, failure_reason = ?
            WHERE canary_id = ?
            """,
            (result, reason[:500], spec.canary_id),
        )
        await db.commit()


async def _canary_rows(db_path: str) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        return await (await db.execute("SELECT * FROM memory_canaries ORDER BY canary_id")).fetchall()


async def _canonical_rows(db_path: str, subject_key: str) -> list[aiosqlite.Row]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        return await (
            await db.execute(
                "SELECT status, temporary, test_marker FROM canonical_memory_items WHERE subject_key = ?",
                (subject_key,),
            )
        ).fetchall()


async def _table_exists(db: aiosqlite.Connection, table: str) -> bool:
    cursor = await db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?", (table,))
    return bool(await cursor.fetchone())


def _spec_for(canary_id: str) -> CanarySpec | None:
    return next((spec for spec in CANARIES if spec.canary_id == canary_id), None)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _past() -> str:
    return (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
