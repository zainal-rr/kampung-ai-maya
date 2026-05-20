from __future__ import annotations

from dataclasses import dataclass

from telegram import BotCommand

from cost_tracker import usage_summary_text
from memory_control import cleanup_stale_memory, forget_memory, memory_sources_text
from provider_readiness import provider_readiness_text
from route_tracker import last_route_text
from screen_session import activate_screen_sight, deactivate_screen_sight, screen_sight_status
from session_compactor import inspect_session_context
from self_healing import self_heal_text
from telegram_status import command_help, status_text
from telegram_voice_state import voice_enabled, voice_text
from vision_session import activate_guided_sight, guided_sight_status


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    args: str = ""


def parse_command(text: str) -> ParsedCommand | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    head, _, args = stripped[1:].partition(" ")
    name = head.split("@", 1)[0].strip().lower()
    return ParsedCommand(name=name, args=args.strip())


def bot_commands() -> list[BotCommand]:
    return [
        BotCommand("help", "Show Maya shortcuts"),
        BotCommand("status", "Show Maya status"),
        BotCommand("imac", "Turn iMac mode on or off"),
        BotCommand("see", "Turn camera guidance on"),
        BotCommand("screen", "Turn screen awareness on or off"),
        BotCommand("project", "Show or close active project"),
        BotCommand("memory", "Show or manage memory"),
        BotCommand("complex", "Route this Telegram request to Maya's complex lane"),
    ]


async def command_to_text(db_path: str, parsed: ParsedCommand) -> str:
    name = parsed.name
    if name == "openimac":
        return "open imac"
    if name == "closeimac":
        return "close imac"
    if name == "imac":
        return _imac_text(parsed.args)
    if name == "remember":
        return _remember_text(parsed.args)
    if name == "see":
        return await activate_guided_sight(db_path)
    if name == "screen":
        return await _screen_command_text(db_path, parsed.args)
    if name == "project":
        return f"/project {parsed.args}".strip()
    if name == "tasks":
        return "what are my tasks?"
    if name == "routines":
        return "show my routines"
    if name == "preferences":
        return "show my preferences"
    if name == "memory":
        return await _memory_text(db_path, parsed.args)
    if name == "forget":
        return await forget_memory(db_path, parsed.args)
    if name == "memorycleanup":
        return await cleanup_stale_memory(db_path)
    if name == "lessons":
        return "what did you learn from me today"
    if name == "skills":
        return "what skills do you have"
    if name == "createskill":
        return _create_skill_text(parsed.args)
    if name == "proposals":
        return "show skill proposals"
    if name == "complex":
        return _complex_text(parsed.args)
    if name == "cost":
        return await usage_summary_text(db_path)
    if name == "providers":
        return provider_readiness_text()
    if name == "route":
        return await last_route_text(db_path)
    if name == "context":
        return await inspect_session_context(db_path)
    if name == "weekly":
        return "weekly reflection"
    if name == "newtopic":
        return "new topic"
    if name == "status":
        return await status_text(db_path)
    if name == "selfheal":
        return await self_heal_text(db_path)
    if name == "voice":
        return await voice_text(db_path, parsed.args)
    if name == "help":
        return command_help()
    return command_help()


def _remember_text(args: str) -> str:
    if not args:
        return "Use /remember followed by what you want me to save."
    lowered = args.lower()
    if lowered.startswith(("that ", "my preference", "i prefer", "remember ")):
        return args
    return f"remember that {args}"


def _create_skill_text(args: str) -> str:
    if not args:
        return "Use /createskill followed by the skill you want Maya to draft."
    return f"create skill for {args}"


def _complex_text(args: str) -> str:
    if not args:
        return "Use /complex followed by the question or decision you want me to think through."
    return f"[complex]{args}"


def _screen_text(args: str) -> str:
    return f"look at my screen: {args}"


async def _screen_command_text(db_path: str, args: str) -> str:
    mode = args.lower().strip()
    if mode in {"off", "close", "stop"}:
        return await deactivate_screen_sight(db_path)
    return _screen_text(args) if args else await activate_screen_sight(db_path)


def _imac_text(args: str) -> str:
    mode = args.lower().strip()
    if mode in {"on", "open", "start", ""}:
        return "open imac"
    if mode in {"off", "close", "stop"}:
        return "close imac"
    return "Use /imac on or /imac off."


async def _memory_text(db_path: str, args: str) -> str:
    cleaned = args.strip()
    lowered = cleaned.lower()
    if lowered == "preferences":
        return "show my preferences"
    if lowered == "lessons":
        return "what did you learn from me today"
    if lowered.startswith("forget "):
        return await forget_memory(db_path, cleaned[7:].strip())
    if lowered in {"cleanup", "clean"}:
        return await cleanup_stale_memory(db_path)
    return await memory_sources_text(db_path, cleaned)

