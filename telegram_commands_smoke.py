from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from lesson_store import init_lesson_db
from routine_store import init_routine_db
from skill_store import init_skill_db
from route_tracker import record_route
from session_memory_store import init_session_memory_db, save_session_summary
from self_heal_store import init_self_heal_db
from storage import init_db
from telegram_commands import bot_commands, command_to_text, parse_command, voice_enabled
from telegram_channel import TelegramChannel


async def main() -> None:
    os.environ["MAYA_EYE_PREVIEW"] = "0"
    os.environ["TELEGRAM_VOICE_LOCKED"] = "1"
    os.environ["TELEGRAM_VOICE_REPLIES"] = "1"
    with tempfile.TemporaryDirectory(prefix="maya-telegram-commands-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)

        parsed = parse_command("/openImac")
        _require(parsed and parsed.name == "openimac", "mixed case command did not parse")
        _require(await command_to_text(db_path, parsed) == "open imac", "openImac did not map")
        visible = [item.command for item in bot_commands()]
        _require(visible == ["help", "status", "imac", "see", "screen", "project", "memory", "complex"], "visible commands not reduced")
        _require(await command_to_text(db_path, parse_command("/imac off")) == "close imac", "imac off did not map")

        remembered = await command_to_text(db_path, parse_command("/remember short replies please"))
        _require(remembered == "remember that short replies please", "remember did not map")
        memory = await command_to_text(db_path, parse_command("/memory"))
        _require("Memory sources:" in memory, "memory command did not return sources")
        _require(await command_to_text(db_path, parse_command("/memory preferences")) == "show my preferences", "memory preferences did not map")
        _require(await command_to_text(db_path, parse_command("/memory lessons")) == "what did you learn from me today", "memory lessons did not map")
        forget_help = await command_to_text(db_path, parse_command("/forget"))
        _require(TelegramChannel._is_direct_command_reply(forget_help), "/forget help should be direct")
        cleanup = await command_to_text(db_path, parse_command("/memorycleanup"))
        _require("Memory cleanup:" in cleanup, "memorycleanup did not run")

        voice_status = await command_to_text(db_path, parse_command("/voice off"))
        _require("locked on" in voice_status and await voice_enabled(db_path), "locked voice status failed")

        see_reply = await command_to_text(db_path, parse_command("/see"))
        _require("visual help" in see_reply or "I can see now" in see_reply, "see did not activate sight")
        _require(TelegramChannel._is_direct_command_reply(see_reply), "/see should be direct")
        screen_reply = await command_to_text(db_path, parse_command("/screen"))
        _require(screen_reply == "I can see your screen now.", "screen did not activate")
        _require(TelegramChannel._is_direct_command_reply(screen_reply), "/screen should be direct")
        screen_off = await command_to_text(db_path, parse_command("/screen off"))
        _require("stopped looking" in screen_off, "screen off did not deactivate")
        screen_question = await command_to_text(db_path, parse_command("/screen explain this slide"))
        _require(screen_question == "look at my screen: explain this slide", "/screen args did not map")
        _require(await command_to_text(db_path, parse_command("/newtopic")) == "new topic", "newtopic did not map")
        _require(await command_to_text(db_path, parse_command("/lessons")) == "what did you learn from me today", "lessons did not map")
        _require(await command_to_text(db_path, parse_command("/skills")) == "what skills do you have", "skills did not map")
        create_skill = await command_to_text(db_path, parse_command("/createskill build better UI"))
        _require(create_skill == "create skill for build better UI", "createskill did not map")
        _require(await command_to_text(db_path, parse_command("/proposals")) == "show skill proposals", "proposals did not map")
        complex_text = await command_to_text(db_path, parse_command("/complex think this through"))
        _require(complex_text == "[complex]think this through", "complex did not map")
        complex_help = await command_to_text(db_path, parse_command("/complex"))
        _require(TelegramChannel._is_direct_command_reply(complex_help), "/complex help should be direct")
        cost = await command_to_text(db_path, parse_command("/cost"))
        _require("Usage estimate" in cost and "Total estimate" in cost, "cost did not summarize usage")
        _require(TelegramChannel._is_direct_command_reply(cost), "/cost should be direct")
        providers = await command_to_text(db_path, parse_command("/providers"))
        _require("Provider readiness:" in providers, "providers did not show readiness")
        _require(TelegramChannel._is_direct_command_reply(providers), "/providers should be direct")
        await record_route(db_path, "text", "Gemini Flash text", "normal Telegram text", False)
        route = await command_to_text(db_path, parse_command("/route"))
        _require("Last route:" in route and "Gemini Flash text" in route, "route did not show last lane")
        _require(TelegramChannel._is_direct_command_reply(route), "/route should be direct")
        await save_session_summary(db_path, "Shared session summary\n1) Test\n a) carried context")
        context = await command_to_text(db_path, parse_command("/context"))
        _require("Context window:" in context and "carried context" in context, "context did not inspect summary")
        _require(TelegramChannel._is_direct_command_reply(context), "/context should be direct")
        _require(await command_to_text(db_path, parse_command("/weekly")) == "weekly reflection", "weekly did not map")
        status = await command_to_text(db_path, parse_command("/status"))
        _require("screen sight" in status and "project:" in status, "status did not report channel state")
        selfheal = await command_to_text(db_path, parse_command("/selfheal"))
        _require("Self heal check:" in selfheal, "selfheal did not run")
        help_text = await command_to_text(db_path, parse_command("/help"))
        _require("Maya commands:" in help_text and "/openimac" in help_text, "help did not show full command map")
        print("telegram_commands_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_self_heal_db(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
