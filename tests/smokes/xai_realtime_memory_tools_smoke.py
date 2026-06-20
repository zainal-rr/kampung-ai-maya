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

from maya_core.storage import init_db
from maya_core.lesson_store import init_lesson_db
from maya_voice.tool_specs import (
    FORGET_MEMORY_TOOL_NAME,
    MAYA_WORK_TOOL_NAME,
    RECALL_MEMORY_TOOL_NAME,
    SAVE_MEMORY_TOOL_NAME,
    voice_tools,
)
from maya_voice.xai_realtime_tools import execute_voice_tool
from maya_voice.xai_voice_work import init_voice_work_db


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _work_count(db_path: str) -> int:
    async with aiosqlite.connect(db_path) as db:
        row = await (await db.execute("SELECT COUNT(*) FROM voice_work_requests")).fetchone()
    return int(row[0])


async def _canonical_rows(db_path: str, pattern: str) -> list[tuple[str, str]]:
    async with aiosqlite.connect(db_path) as db:
        rows = await (
            await db.execute(
                """
                SELECT content, status
                FROM canonical_memory_items
                WHERE lower(content) LIKE lower(?)
                ORDER BY updated_at DESC
                """,
                (pattern,),
            )
        ).fetchall()
    return [(str(row[0]), str(row[1])) for row in rows]


async def _main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "voice-memory.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        await init_voice_work_db(db_path)
        tools = {tool["name"]: tool for tool in voice_tools()}
        _require(SAVE_MEMORY_TOOL_NAME in tools, "save memory tool missing")
        _require(RECALL_MEMORY_TOOL_NAME in tools, "recall memory tool missing")
        _require(FORGET_MEMORY_TOOL_NAME in tools, "forget memory tool missing")
        tool_order = [tool["name"] for tool in voice_tools()]
        _require(tool_order.index(SAVE_MEMORY_TOOL_NAME) < tool_order.index("answer_with_gemini"), "save memory tool must precede Gemini")
        _require(tool_order.index(RECALL_MEMORY_TOOL_NAME) < tool_order.index("answer_with_gemini"), "recall memory tool must precede Gemini")
        _require(tool_order.index(FORGET_MEMORY_TOOL_NAME) < tool_order.index("answer_with_gemini"), "forget memory tool must precede Gemini")
        work_description = str(tools[MAYA_WORK_TOOL_NAME]["description"]).lower()
        _require("memory writes" not in work_description, "generic work tool still advertises memory writes")
        _require("do not use this for memory save" in work_description, "generic work tool lacks memory-save exclusion")
        _require("use the dedicated memory tools instead" in work_description, "generic work tool lacks memory-tool direction")

        before = await _work_count(db_path)
        saved = await execute_voice_tool(
            db_path,
            SAVE_MEMORY_TOOL_NAME,
            {"memory_text": "my realtime memory test notebook color is green"},
        )
        _require("Status: completed" in saved, f"save did not complete: {saved}")
        _require("memory_saved" in saved, f"save result lacked memory proof: {saved}")
        _require(await _work_count(db_path) == before, "memory save created a voice work row")
        rows = await _canonical_rows(db_path, "%realtime memory test notebook color%")
        _require(rows and rows[0][1] == "active", f"canonical save missing/ inactive: {rows}")

        recalled = await execute_voice_tool(
            db_path,
            RECALL_MEMORY_TOOL_NAME,
            {"query": "my realtime memory test notebook color"},
        )
        _require("green" in recalled.lower(), f"recall missed saved fact: {recalled}")
        _require(await _work_count(db_path) == before, "memory recall created a voice work row")

        updated = await execute_voice_tool(
            db_path,
            SAVE_MEMORY_TOOL_NAME,
            {"memory_text": "my realtime memory test notebook color is blue"},
        )
        _require("Status: completed" in updated, f"update did not complete: {updated}")
        recalled = await execute_voice_tool(
            db_path,
            RECALL_MEMORY_TOOL_NAME,
            {"query": "my realtime memory test notebook color"},
        )
        _require("blue" in recalled.lower(), f"updated fact did not win: {recalled}")
        _require("green" not in recalled.lower(), f"superseded value leaked in direct recall: {recalled}")

        forgotten = await execute_voice_tool(
            db_path,
            FORGET_MEMORY_TOOL_NAME,
            {"query": "my realtime memory test notebook color"},
        )
        _require("Removed" in forgotten, f"forget did not remove canonical memory: {forgotten}")
        recalled = await execute_voice_tool(
            db_path,
            RECALL_MEMORY_TOOL_NAME,
            {"query": "my realtime memory test notebook color"},
        )
        _require("memory_not_found" in recalled, f"forgotten fact leaked after forget: {recalled}")
        _require(await _work_count(db_path) == before, "memory forget created a voice work row")

        absent = await execute_voice_tool(
            db_path,
            RECALL_MEMORY_TOOL_NAME,
            {"query": "my realtime memory test hotel chain"},
        )
        _require("memory_not_found" in absent, f"absent memory guessed: {absent}")

    print("xai_realtime_memory_tools_smoke: ok")


if __name__ == "__main__":
    asyncio.run(_main())
