from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from assistant import KampungAssistant
from briefing_service import BriefingBuilder
from lesson_store import add_lesson, init_lesson_db
from routine_store import init_routine_db
from skill_store import init_skill_db
from storage import create_task, init_db, save_history_message, upsert_preference
from storage import update_task_status
from weekly_memory import WeeklyMemoryDistiller
from weekly_memory_store import init_weekly_memory_db, latest_weekly_summary


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-weekly-memory-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)
        await _seed(db_path)

        dry = await WeeklyMemoryDistiller(db_path).run(save=False)
        _require("Provider calls used: none" in dry.summary, "dry run should not need providers")
        _require("short Telegram replies" in dry.summary, "preferences were not included")
        _require("Recent conversation topics:" in dry.summary, "conversation topics were not summarized")
        _require("quantum computing" in dry.summary and "spin" in dry.summary, "voice-style Telegram topics were missed")
        _require("6429253538" not in dry.summary, "internal chat id leaked into weekly memory")
        _require("Create skill scaffold" not in dry.summary, "pending scaffold leaked into open loops")
        _require(not dry.saved, "dry run should not save unless requested")

        saved = await WeeklyMemoryDistiller(db_path).run(save=True)
        latest = await latest_weekly_summary(db_path)
        _require(saved.saved and latest is not None, "weekly summary was not saved")
        _require(latest["run_key"] == saved.run_key, "saved run key mismatch")

        reflection = await BriefingBuilder(db_path).build("weekly_reflection", "telegram")
        _require("Weekly memory dry run" in reflection, "weekly reflection missed prepared summary")
        natural = await KampungAssistant(db_path).handle_text("what did you learn this week", "telegram")
        _require("Weekly memory dry run" in natural, "natural weekly question missed prepared summary")
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


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
