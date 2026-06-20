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

from maya_core.learning_pipeline import LearningPipeline
from maya_core.lesson_store import init_lesson_db
from maya_memory.memory_extraction import deterministic_extraction, extract_memory_fields
from maya_memory.memory_service import MemoryService
from maya_core.storage import init_db


async def main() -> None:
    # 1) No agent: deterministic result, identical to legacy regex behavior.
    result = await extract_memory_fields("my favourite snack is kuih lapis")
    _require(result.source == "deterministic", "no-agent extraction must be deterministic")
    _require(result.subject == "favourite_snack", f"unexpected subject: {result.subject}")
    _require(result.value == "kuih lapis", f"unexpected value: {result.value}")
    _require(result.durable, "plain fact wrongly marked non-durable")

    # 2) Valid provider JSON is accepted and normalized.
    async def good_agent(_prompt: str) -> str:
        return '{"subject":"favourite snack","value":"kuih lapis","kind":"profile_fact","scope":"global","durable":true,"sensitive":false}'

    result = await extract_memory_fields("my favourite snack is kuih lapis", good_agent)
    _require(result.source == "provider", "valid provider output was not used")
    _require(result.kind == "profile_fact", f"kind not honored: {result.kind}")
    _require(result.subject == "favourite_snack", f"subject not normalized: {result.subject}")

    # 3) Hallucinated subject (no overlap with source) falls back.
    async def hallucinating_agent(_prompt: str) -> str:
        return '{"subject":"blood type","value":"O positive","kind":"profile_fact","scope":"global","durable":true,"sensitive":false}'

    result = await extract_memory_fields("my favourite snack is kuih lapis", hallucinating_agent)
    _require(result.source == "deterministic", "hallucinated subject was accepted")

    # 4) Malformed JSON, bad kind, provider crash: all fall back.
    async def broken_agent(_prompt: str) -> str:
        return "sorry, I cannot do JSON today"

    async def bad_kind_agent(_prompt: str) -> str:
        return '{"subject":"favourite snack","value":"kuih lapis","kind":"random_kind","scope":"global"}'

    async def crashing_agent(_prompt: str) -> str:
        raise RuntimeError("provider down")

    for agent in (broken_agent, bad_kind_agent, crashing_agent):
        result = await extract_memory_fields("my favourite snack is kuih lapis", agent)
        _require(result.source == "deterministic", f"{agent.__name__} did not fall back")

    # 5) Provider sensitive flag is honored (OR-ed, never replaced).
    async def sensitive_agent(_prompt: str) -> str:
        return '{"subject":"favourite snack","value":"kuih lapis","kind":"profile_fact","scope":"global","durable":true,"sensitive":true}'

    result = await extract_memory_fields("my favourite snack is kuih lapis", sensitive_agent)
    _require(result.sensitive, "provider sensitive flag was dropped")

    # 6) Local sensitive detection cannot be overridden by provider.
    local = deterministic_extraction("my bank password is hunter2")
    _require(local.sensitive, "local sensitive detection failed")

    # 7) End to end through LearningPipeline: provider extraction shapes the
    # save and the reply echoes subject -> value (visibility contract).
    with tempfile.TemporaryDirectory(prefix="maya-extraction-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        pipeline = LearningPipeline(db_path, extraction_agent=good_agent)
        reply = await pipeline.handle("remember that my favourite snack is kuih lapis", "telegram")
        _require(reply is not None and "saved" in reply.lower(), "explicit save failed")
        _require("favourite_snack -> kuih lapis" in reply, f"reply missing subject/value echo: {reply}")
        recalled = await MemoryService(db_path).search_direct_fact("what is my favourite snack")
        _require(recalled == ["my favourite snack is kuih lapis"], f"recall after extraction save failed: {recalled}")

        # No-agent pipeline must behave exactly as before, no echo.
        pipeline_plain = LearningPipeline(db_path, extraction_agent=None)
        _require(pipeline_plain.extraction_agent is None or callable(pipeline_plain.extraction_agent), "agent wiring broken")
        reply = await pipeline_plain.handle("remember that my telegram test drink is teh ais", "telegram")
        _require(reply is not None and "saved" in reply.lower(), "legacy save failed")

        # 8) Shadow mode: provider runs and divergence is audited, but the
        # deterministic parse is saved and no echo appears in the reply.
        async def diverging_agent(_prompt: str) -> str:
            return '{"subject":"morning kopi","value":"kopi o kosong","kind":"profile_fact","scope":"global","durable":true,"sensitive":false}'

        shadow = LearningPipeline(db_path, extraction_agent=diverging_agent, extraction_live=False)
        reply = await shadow.handle("remember that my morning kopi order is kopi o kosong", "telegram")
        _require(reply is not None and "saved" in reply.lower(), "shadow save failed")
        _require("(saved as" not in reply, "shadow mode must not echo provider parse")
        recalled = await MemoryService(db_path).search_direct_fact("what is my morning kopi order")
        _require(recalled == ["my morning kopi order is kopi o kosong"], f"shadow recall failed: {recalled}")
        import aiosqlite

        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            rows = await (
                await db.execute(
                    "SELECT status_after, source_ref FROM memory_audit_events WHERE event_type = 'extraction_divergence'"
                )
            ).fetchall()
        _require(bool(rows), "shadow mode wrote no divergence audit event")
        _require("mode=shadow" in rows[-1]["source_ref"], f"divergence audit missing mode: {rows[-1]['source_ref']}")
        _require("outcome=accepted" in rows[-1]["source_ref"], f"divergence audit missing outcome: {rows[-1]['source_ref']}")
        _require(rows[-1]["status_after"] == "diverged", "subject divergence not flagged")
        _require("subj_div=" in rows[-1]["source_ref"] and "sens_div=" in rows[-1]["source_ref"] and "dur_div=" in rows[-1]["source_ref"],
                 f"per-dimension divergence flags missing: {rows[-1]['source_ref']}")

    print("memory_extraction_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
