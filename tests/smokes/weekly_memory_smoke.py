from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import json
import tempfile
from pathlib import Path

from assistant import KampungAssistant
from briefing_service import BriefingBuilder
from canonical_memory_inspector import inspect_canonical_memory
from lesson_store import add_lesson, init_lesson_db
from routine_store import init_routine_db
from skill_store import init_skill_db
from storage import create_task, init_db, save_history_message, upsert_preference
from storage import update_task_status
from telegram_commands import ParsedCommand, command_to_text
from weekly_memory import WeeklyMemoryDistiller
from weekly_memory_store import init_weekly_memory_db, latest_weekly_memory_runs, latest_weekly_summary


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-weekly-memory-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        await _seed(db_path)

        dry = await WeeklyMemoryDistiller(db_path).run(save=False)
        _require("Provider calls used: none" in dry.summary, "dry run should not need providers")
        _require(dry.run_audit_id > 0, "dry weekly run did not create an audit record")
        _require("short Telegram replies" in dry.summary, "preferences were not included")
        _require("Recent conversation topics:" in dry.summary, "conversation topics were not summarized")
        _require("quantum computing" in dry.summary and "spin" in dry.summary, "voice-style Telegram topics were missed")
        _require("6429253538" not in dry.summary, "internal chat id leaked into weekly memory")
        _require("Create skill scaffold" not in dry.summary, "pending scaffold leaked into open loops")
        _require(not dry.saved, "dry run should not save unless requested")

        saved = await WeeklyMemoryDistiller(db_path).run(save=True)
        latest = await latest_weekly_summary(db_path)
        _require(saved.saved and latest is not None, "weekly summary was not saved")
        saved_runs = await latest_weekly_memory_runs(db_path, limit=3)
        _require(saved_runs and saved_runs[0]["status"] == "completed", "saved weekly run was not audited as completed")
        _require(saved_runs[0]["trigger_source"] == "manual", "manual weekly run trigger source mismatch")
        _require(latest["run_key"] == saved.run_key, "saved run key mismatch")
        _require(saved.canonical_memory_ids, "weekly report did not expose canonical memory IDs")
        _require("Canonical memory IDs used:" in saved.summary, "weekly summary did not mention canonical memory IDs")
        _require(json.loads(str(latest["canonical_memory_ids"])), "weekly summary storage did not record canonical IDs")
        live = await WeeklyMemoryDistiller(db_path).run(
            save=True,
            live=True,
            trigger_source="smoke",
            distiller_agent=_fake_distiller,
            reviewer_agent=_fake_reviewer,
        )
        live_runs = await latest_weekly_memory_runs(db_path, limit=1)
        _require(live_runs and live_runs[0]["trigger_source"] == "smoke", "live weekly audit trigger source mismatch")
        _require(live_runs[0]["provider_calls"] == 2, "live weekly audit provider call count mismatch")
        latest_live = await latest_weekly_summary(db_path)
        _require(live.provider_calls == 2, "live weekly memory should call distiller and reviewer")
        _require(live.canonical_saved == 1, "live weekly memory should save approved canonical fact")
        _require(live.canonical_rejected == 2, "weekly memory should reject unsafe, temporary, and transient artifact facts")
        _require(live.confirmation_needed == ("Zainal may prefer very detailed weekly summaries",), "Claude weekly review should surface confirmation-needed facts")
        _require(any(item.startswith("mem_") for item in live.canonical_memory_ids), "live weekly memory did not return memory IDs")
        _require(latest_live and latest_live["source"] == "live_provider", "live weekly summary source mismatch")
        _require(len(json.loads(str(latest_live["canonical_memory_ids"]))) >= len(live.canonical_memory_ids), "live weekly summary did not store memory IDs")
        inspected = await inspect_canonical_memory(db_path, "concise weekly summary bullets")
        _require("I prefer concise weekly summary bullets" in inspected, "live weekly memory did not write canonical fact")
        rejected = await inspect_canonical_memory(db_path, "weekly test fruit")
        _require("No canonical memory found" in rejected, "live weekly memory saved a rejected test fact")

        fallback = await WeeklyMemoryDistiller(db_path).run(
            save=True,
            live=True,
            trigger_source="smoke-reviewer-fallback",
            distiller_agent=_fake_distiller,
            reviewer_agent=_failing_reviewer,
        )
        fallback_runs = await latest_weekly_memory_runs(db_path, limit=1)
        _require(fallback.provider_calls == 2, "reviewer fallback should count distiller plus reviewer attempt")
        _require(fallback.canonical_saved == 0, "reviewer fallback must not save unreviewed canonical facts")
        _require(fallback.canonical_rejected >= 1, "reviewer fallback should reject proposed unreviewed facts")
        _require("Reviewer unavailable" in fallback.summary, "reviewer fallback warning missing from summary")
        _require(fallback_runs and fallback_runs[0]["status"] == "completed", "reviewer fallback should complete audit row")
        _require("RuntimeError: reviewer unavailable" in str(fallback_runs[0]["error"]), "reviewer fallback error was not audited")

        reflection = await BriefingBuilder(db_path).build("weekly_reflection", "telegram")
        _require("Weekly reflection." in reflection, "weekly reflection missed title")
        _require("What I kept:" in reflection, "weekly reflection missed clean memory takeaway")
        _require("Weekly memory live run" not in reflection, "weekly reflection leaked raw run header")
        _require("Provider calls" not in reflection, "weekly reflection leaked provider debug text")
        _require("Canonical memory IDs" not in reflection, "weekly reflection leaked canonical IDs")
        _require("/Users/" not in reflection and "{" not in reflection, "weekly reflection leaked raw path or JSON")
        weekly_status = await command_to_text(db_path, ParsedCommand("weekly", "status"))
        _require("Weekly memory status:" in weekly_status, "/weekly status did not return audit status")
        _require("smoke" in weekly_status, "/weekly status did not show trigger source")
        natural = await KampungAssistant(db_path).handle_text("what did you learn this week", "telegram")
        _require("What I kept:" in natural, "natural weekly question missed clean weekly reflection")
        _require("Provider calls" not in natural, "natural weekly question leaked provider debug text")
        print("weekly_memory_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_weekly_memory_db(db_path)


async def _seed(db_path: str) -> None:
    await save_history_message(db_path, 1, "user", "Remember that Telegram should stay short.", "telegram")
    await save_history_message(db_path, 1, "user", "Hi Maya, can you tell me what quantum computing is?", "telegram")
    await save_history_message(db_path, 1, "assistant", "Quantum computing uses qubits, superposition, and entanglement.", "telegram")
    await save_history_message(db_path, 1, "user", "What spin are you talking about?", "telegram")
    await save_history_message(db_path, 1, "assistant", "Spin here is the quantum particle property connected to qubits.", "telegram")
    await upsert_preference(db_path, "telegram_reply_length", "short Telegram replies unless the task is complex")
    await add_lesson(
        db_path,
        "I am teaching you to avoid dashes.",
        "no dash symbols in answers",
        "preference",
        "formatting",
        "explicit",
        "high",
        "telegram",
        "formatting_no_dash",
    )
    await create_task(db_path, title="check hosting renewal", channel="telegram")
    scaffold = await create_task(
        db_path,
        title="Create skill scaffold for Cancel",
        channel="telegram",
        action_type="create_skill_scaffold",
    )
    await update_task_status(db_path, scaffold, "awaiting_confirmation")
    await upsert_preference(db_path, "telegram_chat_id", "6429253538")


async def _fake_distiller(_prompt: str) -> str:
    return """
    {"facts":[
      {"content":"I prefer concise weekly summary bullets","kind":"preference","scope":"global","confidence":"high"},
      {"content":"Maya is planning a 48-hour food-focused trip to Seoul for one traveler","kind":"project_fact","scope":"global","confidence":"high"},
      {"content":"my weekly test fruit is rambutan","kind":"preference","scope":"global","confidence":"high"},
      {"content":"Zainal may prefer very detailed weekly summaries","kind":"preference","scope":"global","confidence":"medium"}
    ]}
    """


async def _fake_reviewer(_prompt: str) -> str:
    return """
    {
      "facts":[
        {"content":"I prefer concise weekly summary bullets","kind":"preference","scope":"global","confidence":"high"},
        {"content":"Maya is planning a 48-hour food-focused trip to Seoul for one traveler","kind":"project_fact","scope":"global","confidence":"high"}
      ],
      "rejected":[
        {"content":"my weekly test fruit is rambutan","reason":"temporary test memory"}
      ],
      "confirmation_needed":[
        {"content":"Zainal may prefer very detailed weekly summaries","reason":"preference is uncertain and contradicts existing concise preference"}
      ]
    }
    """


async def _failing_reviewer(_prompt: str) -> str:
    raise RuntimeError("reviewer unavailable")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
