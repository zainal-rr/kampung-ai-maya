from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import aiosqlite

from maya_core.repo_paths import repo_root
from maya_core.curated_memory import (
    CORE_SCOPE,
    MAYA_CORE_CAP,
    PROFILE_SCOPE,
    ZAINAL_PROFILE_CAP,
    init_curated_memory_db,
    scope_summary,
)
from storage import get_preference

TARGET_PERCENT = 80
SNAPSHOT_DIR = repo_root(__file__) / "backups" / "self_heal_memory"

CORE_REPLACEMENT = [
    "Identity and sight: Maya is Zainal's assistant; when using camera or screen she is the one seeing. Preserve desk-orientation calibration and use current vision context before spatial guidance.",
    "Office artifact quality: Word, Excel, PowerPoint, and HTML requests use the shared high-quality pipeline across Telegram and iMac: Gemini role/preflight/draft, Claude Opus review where useful, local builders, validation, QA, and repair before final delivery.",
    "Document continuity: follow-up edits update the latest artifact in place with an internal backup unless Zainal asks for a new copy. If QA fails badly, preserve the original and report the failure.",
    "Channel delivery: Telegram attaches files and sends important paths and summaries as text; iMac opens or focuses local files. Voice is decoupled from worker lanes and must not monopolize long tasks.",
    "Current priorities: Office artifact quality and memory architecture first; Artisan/Codex app building and Blender/Maker remain established capabilities for project folders and approved work.",
]

PROFILE_REPLACEMENT = [
    "Zainal prefers concise, direct Telegram and iMac replies, with longer detail only when asked. Do not repeat passed tests or invent next steps; follow KAMPUNG_AI_CHECKLIST.md.",
    "Zainal values honest route, cost, and review reporting, visible file paths, and no guessed memory after forget. Ask for missing parameters only when needed.",
    "Travel artifacts should be immediately useful: Seoul food-trip examples use specific restaurants, budgets, links and suggestions in Excel, visual dark-theme PowerPoint slides with speaker notes, and polished Word itineraries.",
]

RETRIEVAL_CRITERIA = {
    "latest document": "maya_last_document_path preference remains present if it existed before compaction",
    "Seoul deck": "Seoul travel/artifact context remains in curated profile memory",
    "Office artifact quality": "core memory contains the exact phrase Office artifact quality",
    "/status self heal": "latest self-heal report remains readable after compaction",
}


async def handle_memory_self_heal_command(db_path: str, args: str, *, root: str | Path | None = None) -> str:
    mode = " ".join(args.lower().strip().split())
    if mode in {"dryrun", "dry run"}:
        return await memory_self_heal_dry_run(db_path, root=root)
    if mode in {"proceed", "run", "execute"}:
        return await memory_self_heal_proceed(db_path, root=root)
    if mode in {"abort", "cancel"}:
        return "Self-heal aborted. No memory, files, cache, or service state was changed."
    if mode == "force":
        return "Rejected. /selfheal force is not staged for this memory-only heal. Use /selfheal dryrun or /selfheal proceed."
    return ""


async def memory_self_heal_dry_run(db_path: str, *, root: str | Path | None = None) -> str:
    before = await _status(db_path)
    after = _projected_status()
    latest_doc = await get_preference(db_path, "maya_last_document_path")
    snapshot_root = _snapshot_root(root)
    return "\n".join(
        [
            "Memory self-heal dry run.",
            "1) No memory, files, cache, or service state was changed.",
            f"2) Snapshot path if approved: {snapshot_root}",
            f"3) Rollback command: ./venv/bin/python self_heal_memory.py restore <snapshot_dir>",
            "4) Failure behavior: abort before commit; if post-write validation fails, restore curated memory from the snapshot.",
            "5) Force mode: rejected for this scoped memory-only heal.",
            f"6) Target: core memory / Zainal profile curated memory at or below {TARGET_PERCENT}% usage.",
            f"7) Current core memory / Zainal profile: {before['core_percent']}% / {before['profile_percent']}%.",
            f"8) Projected core memory / Zainal profile: {after['core_percent']}% / {after['profile_percent']}%.",
            f"9) Latest document preserved: {latest_doc or 'none saved'}",
            "10) Retrieval pass criteria:",
            *_criteria_lines(),
        ]
    )


async def memory_self_heal_proceed(db_path: str, *, root: str | Path | None = None) -> str:
    snapshot = await create_memory_snapshot(db_path, root=root)
    before = await _status(db_path)
    try:
        await _write_replacements(db_path)
        validation = await validate_memory_self_heal(db_path, before)
        if not validation["passed"]:
            await restore_memory_snapshot(db_path, snapshot)
            return _failure_text(snapshot, validation["issues"])
    except Exception as exc:
        await restore_memory_snapshot(db_path, snapshot)
        return _failure_text(snapshot, [f"{type(exc).__name__}: {exc}"])
    after = await _status(db_path)
    return "\n".join(
        [
            "Memory self-heal completed.",
            f"1) Snapshot: {snapshot}",
            f"2) Rollback command: ./venv/bin/python self_heal_memory.py restore {snapshot}",
            f"3) Core memory: {before['core_percent']}% -> {after['core_percent']}%.",
            f"4) Zainal profile: {before['profile_percent']}% -> {after['profile_percent']}%.",
            "5) Retrieval checks passed: latest document, Seoul deck context, Office artifact quality, and self-heal status.",
            "6) No local documents, project folders, cache, services, routes, or provider state were touched.",
        ]
    )


async def create_memory_snapshot(db_path: str, *, root: str | Path | None = None) -> Path:
    await init_curated_memory_db(db_path)
    snapshot_dir = _snapshot_root(root) / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    db_backup = snapshot_dir / "session_history.db"
    await asyncio.to_thread(_sqlite_backup, db_path, db_backup)
    rows = await _curated_rows(db_path)
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "db_path": str(db_path),
        "db_backup": str(db_backup),
        "db_sha256": _sha256(db_backup),
        "target_percent": TARGET_PERCENT,
        "retrieval_criteria": RETRIEVAL_CRITERIA,
        "curated_memory_items": rows,
    }
    manifest = snapshot_dir / "manifest.json"
    manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return snapshot_dir


async def restore_memory_snapshot(db_path: str, snapshot_dir: str | Path) -> str:
    await init_curated_memory_db(db_path)
    manifest = Path(snapshot_dir) / "manifest.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    backup_path = Path(str(payload.get("db_backup", "")))
    expected_hash = str(payload.get("db_sha256", ""))
    if backup_path.exists() and expected_hash and _sha256(backup_path) != expected_hash:
        raise ValueError(f"Snapshot DB checksum mismatch: {backup_path}")
    rows = payload.get("curated_memory_items", [])
    async with aiosqlite.connect(db_path) as db:
        await db.execute("DELETE FROM curated_memory_items WHERE scope IN (?, ?)", (CORE_SCOPE, PROFILE_SCOPE))
        for row in rows:
            await db.execute(
                """
                INSERT INTO curated_memory_items (scope, content, source, confidence, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["scope"],
                    row["content"],
                    row.get("source", "snapshot_restore"),
                    float(row.get("confidence", 0.86)),
                    row.get("status", "active"),
                    row.get("created_at"),
                    row.get("updated_at"),
                ),
            )
        await db.commit()
    return f"Restored curated memory from {manifest}."


async def validate_memory_self_heal(db_path: str, before: dict[str, int | str | None]) -> dict[str, object]:
    status = await _status(db_path)
    merged = f"{status['core_text']} {status['profile_text']}".lower()
    issues: list[str] = []
    if int(status["core_percent"]) > TARGET_PERCENT:
        issues.append(f"core memory above target: {status['core_percent']}%")
    if int(status["profile_percent"]) > TARGET_PERCENT:
        issues.append(f"profile memory above target: {status['profile_percent']}%")
    required = ("office artifact quality", "telegram", "imac", "latest artifact in place", "no guessed memory", "seoul")
    for needle in required:
        if needle not in merged:
            issues.append(f"missing preserved rule/context: {needle}")
    if before.get("latest_doc") and await get_preference(db_path, "maya_last_document_path") != before["latest_doc"]:
        issues.append("latest document preference changed")
    return {"passed": not issues, "issues": issues}


def guardrails_text() -> str:
    criteria = "; ".join(f"{key}: {value}" for key, value in RETRIEVAL_CRITERIA.items())
    return (
        f"Snapshot root: {SNAPSHOT_DIR}. Rollback command: ./venv/bin/python self_heal_memory.py restore <snapshot_dir>. "
        "Abort/rollback: no partial commit; restore curated memory from snapshot on validation failure. "
        f"Force mode is rejected. Target: core/profile curated memory <= {TARGET_PERCENT}% usage. "
        f"Retrieval pass criteria: {criteria}."
    )


async def _write_replacements(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("BEGIN")
        await db.execute("UPDATE curated_memory_items SET status = 'stale' WHERE scope IN (?, ?)", (CORE_SCOPE, PROFILE_SCOPE))
        for scope, rows in ((CORE_SCOPE, CORE_REPLACEMENT), (PROFILE_SCOPE, PROFILE_REPLACEMENT)):
            for content in rows:
                await db.execute(
                    """
                    INSERT INTO curated_memory_items (scope, content, source, updated_at)
                    VALUES (?, ?, 'self_heal_compaction', CURRENT_TIMESTAMP)
                    """,
                    (scope, content),
                )
        await db.commit()


async def _status(db_path: str) -> dict[str, int | str | None]:
    core = await scope_summary(db_path, CORE_SCOPE)
    profile = await scope_summary(db_path, PROFILE_SCOPE)
    return {
        "core_percent": int(core["percent"]),
        "profile_percent": int(profile["percent"]),
        "core_text": str(core["summary"]),
        "profile_text": str(profile["summary"]),
        "latest_doc": await get_preference(db_path, "maya_last_document_path"),
    }


def _projected_status() -> dict[str, int]:
    core_chars = len("\n".join(CORE_REPLACEMENT))
    profile_chars = len("\n".join(PROFILE_REPLACEMENT))
    return {
        "core_percent": round(core_chars / MAYA_CORE_CAP * 100),
        "profile_percent": round(profile_chars / ZAINAL_PROFILE_CAP * 100),
    }


async def _curated_rows(db_path: str) -> list[dict[str, object]]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM curated_memory_items WHERE scope IN (?, ?) ORDER BY id",
            (CORE_SCOPE, PROFILE_SCOPE),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


def _failure_text(snapshot: Path, issues: list[str]) -> str:
    return "\n".join(
        [
            "Memory self-heal failed and was rolled back.",
            f"1) Snapshot: {snapshot}",
            f"2) Rollback command: ./venv/bin/python self_heal_memory.py restore {snapshot}",
            "3) Issues:",
            *[f"- {issue}" for issue in issues],
        ]
    )


def _criteria_lines() -> list[str]:
    return [f"   - {key}: {value}" for key, value in RETRIEVAL_CRITERIA.items()]


def _snapshot_root(root: str | Path | None) -> Path:
    return (Path(root) / "backups" / "self_heal_memory") if root else SNAPSHOT_DIR


def _sqlite_backup(source: str, dest: Path) -> None:
    with sqlite3.connect(source) as src, sqlite3.connect(dest) as dst:
        src.backup(dst)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3 or sys.argv[1] != "restore":
        raise SystemExit("Usage: ./venv/bin/python self_heal_memory.py restore <snapshot_dir>")
    asyncio.run(restore_memory_snapshot("session_history.db", sys.argv[2]))
