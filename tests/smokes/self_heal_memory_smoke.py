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

from maya_core.curated_memory import CORE_SCOPE, PROFILE_SCOPE, init_curated_memory_db, scope_summary
from maya_core.self_heal_memory import handle_memory_self_heal_command, restore_memory_snapshot
from maya_core.storage import get_preference, init_db, upsert_preference
from maya_telegram.telegram_commands import command_to_text, parse_command


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        db_path = str(root / "maya.db")
        await init_db(db_path)
        await init_curated_memory_db(db_path)
        await _seed_memory(db_path)
        last_doc = str(root / "seoul-food-trip-deck-v14.pptx")
        Path(last_doc).write_bytes(b"pptx")
        await upsert_preference(db_path, "maya_last_document_path", last_doc, "smoke")

        dryrun = await handle_memory_self_heal_command(db_path, "dryrun", root=root)
        _require("No memory" in dryrun and "Rollback command" in dryrun, "dryrun should not write and must show rollback")
        _require("core memory" in dryrun.lower() and "zainal profile" in dryrun.lower(), "dryrun should name core/profile memory explicitly")
        _require("latest document" in dryrun and "Office artifact quality" in dryrun, "dryrun missing pass criteria")

        force = await command_to_text(db_path, parse_command("/selfheal force"))
        _require("Rejected" in force and "not staged" in force, "force mode must be rejected")

        result = await handle_memory_self_heal_command(db_path, "proceed", root=root)
        _require("Memory self-heal completed" in result, "proceed did not complete")
        _require("Rollback command" in result, "proceed missing rollback command")
        _require(await get_preference(db_path, "maya_last_document_path") == last_doc, "latest document changed")

        core = await scope_summary(db_path, CORE_SCOPE)
        profile = await scope_summary(db_path, PROFILE_SCOPE)
        _require(int(core["percent"]) <= 80, "core memory above target")
        _require(int(profile["percent"]) <= 80, "profile memory above target")
        merged = f"{core['summary']} {profile['summary']}".lower()
        _require("office artifact quality" in merged, "office quality rule lost")
        _require("seoul" in merged, "seoul context lost")
        _require("no guessed memory" in merged, "memory no-guess rule lost")

        snapshots = sorted((root / "backups" / "self_heal_memory").iterdir())
        _require(snapshots and (snapshots[-1] / "manifest.json").exists(), "snapshot manifest missing")
        await restore_memory_snapshot(db_path, snapshots[-1])
        _require(await _source_count(db_path, "smoke") >= 2, "snapshot restore did not restore original rows")
    print("self_heal_memory_smoke: ok")


async def _seed_memory(db_path: str) -> None:
    noisy_core = "can you hear me voice transcript loop. " * 40
    profile_noise = "old Telegram test fragment. " * 35
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO curated_memory_items (scope, content, source) VALUES (?, ?, 'smoke')",
            (CORE_SCOPE, noisy_core),
        )
        await db.execute(
            "INSERT INTO curated_memory_items (scope, content, source) VALUES (?, ?, 'smoke')",
            (PROFILE_SCOPE, profile_noise),
        )
        await db.commit()


async def _source_count(db_path: str, source: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM curated_memory_items WHERE source = ?", (source,))
        row = await cursor.fetchone()
    return int(row[0])


if __name__ == "__main__":
    asyncio.run(main())
