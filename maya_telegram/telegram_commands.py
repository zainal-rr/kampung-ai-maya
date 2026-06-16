from __future__ import annotations

from dataclasses import dataclass

from telegram import BotCommand

from maya_documents.artifact_review_store import latest_artifact_review_text, resolve_review_activity_text
from maya_core.artisan_apply import apply_latest_artisan_repo_changes
from maya_core.artisan_runner import latest_artisan_delivery_text, latest_artisan_summary_text, latest_artisan_transcript_text
from maya_core.cost_tracker import usage_summary_text
from maya_memory.canonical_memory_inspector import inspect_canonical_memory
from maya_memory.canonical_memory_migration import migrate_memory_to_canonical
from maya_memory.canonical_memory_pin import set_canonical_memory_pin
from maya_memory.memory_control import cleanup_stale_memory, forget_memory, memory_sources_text
from maya_core.provider_readiness import provider_readiness_text
from maya_core.route_tracker import last_route_text
from maya_core.screen_session import activate_screen_sight, deactivate_screen_sight, screen_sight_status, toggle_screen_sight
from maya_core.session_compactor import inspect_session_context
from maya_core.self_healing import self_heal_text
from maya_core.self_heal_memory import handle_memory_self_heal_command
from maya_telegram.telegram_status import command_help, status_text
from maya_telegram.telegram_delivery_log import latest_telegram_delivery_text
from maya_telegram.telegram_turn_log import latest_telegram_turn_text
from maya_telegram.telegram_voice_state import voice_enabled, voice_text
from maya_core.vision_session import guided_sight_status, toggle_guided_sight
from maya_core.weekly_memory_status import run_weekly_memory_now_text, weekly_memory_status_text
from maya_core.repo_paths import repo_root


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    args: str = ""


PASSTHROUGH_COMMANDS = {
    "remember",
    "createskill",
    "project",
    "tasks",
    "routines",
    "preferences",
    "lessons",
    "skills",
    "newtopic",
}


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
        BotCommand("see", "Toggle camera guidance on or off"),
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
        return await toggle_guided_sight(db_path)
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
    if name == "memorymigrate":
        return await migrate_memory_to_canonical(db_path)
    if name == "memoryinspect":
        return await inspect_canonical_memory(db_path, parsed.args)
    if name == "memorypin":
        return await set_canonical_memory_pin(db_path, parsed.args, pinned=True)
    if name == "memoryunpin":
        return await set_canonical_memory_pin(db_path, parsed.args, pinned=False)
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
    if name in {"delivery", "lastdelivery"}:
        return await latest_telegram_delivery_text(db_path)
    if name in {"turn", "lastturn"}:
        return await latest_telegram_turn_text(db_path)
    if name in {"review", "artifactreview", "artifactqa"}:
        resolved = await resolve_review_activity_text(db_path, f"review {parsed.args}".strip())
        if resolved:
            return resolved
        return await latest_artifact_review_text(db_path)
    if name == "context":
        return await inspect_session_context(db_path)
    if name == "weekly":
        return await _weekly_text(db_path, parsed.args)
    if name == "artisan":
        return await _artisan_text(db_path, parsed.args)
    if name == "newtopic":
        return "new topic"
    if name == "status":
        return await status_text(db_path)
    if name == "selfheal":
        scoped = await handle_memory_self_heal_command(db_path, parsed.args, root=repo_root(__file__))
        return scoped or await self_heal_text(db_path)
    if name == "voice":
        return await voice_text(db_path, parsed.args)
    if name == "help":
        return command_help()
    return f"/{name} is not in the command list. Use /help to see available commands."


def _remember_text(args: str) -> str:
    if not args:
        return "Use /remember followed by what you want me to save."
    lowered = args.lower()
    if lowered.startswith("remember "):
        return args
    if lowered.startswith("that "):
        return f"remember {args}"
    if lowered.startswith(("my preference", "i prefer")):
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


async def _artisan_text(db_path: str, args: str) -> str:
    mode = args.lower().strip()
    if mode in {"transcript", "log"}:
        return await latest_artisan_transcript_text(db_path)
    if mode in {"app", "last app", "latest app"}:
        return await latest_artisan_delivery_text(db_path, "app", "telegram")
    if mode in {"maker", "3d", "3d model", "last 3d", "latest 3d"}:
        return await latest_artisan_delivery_text(db_path, "maker", "telegram")
    if mode in {"apply", "apply latest", "apply repo", "apply changes"}:
        return await apply_latest_artisan_repo_changes(db_path)
    return await latest_artisan_summary_text(db_path)


def _screen_text(args: str) -> str:
    return f"look at my screen: {args}"


async def _screen_command_text(db_path: str, args: str) -> str:
    mode = args.lower().strip()
    if mode in {"off", "close", "stop"}:
        return "Use /screen to toggle screen awareness on or off."
    return _screen_text(args) if args else await toggle_screen_sight(db_path)


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
    if lowered in {"migrate", "migration", "canonical migrate"}:
        return await migrate_memory_to_canonical(db_path)
    if lowered in {"inspect", "ids", "canonical"}:
        return await inspect_canonical_memory(db_path)
    if lowered.startswith(("inspect ", "ids ", "canonical ")):
        return await inspect_canonical_memory(db_path, cleaned.split(" ", 1)[1].strip())
    if lowered.startswith("pin "):
        return await set_canonical_memory_pin(db_path, cleaned[4:].strip(), pinned=True)
    if lowered.startswith("unpin "):
        return await set_canonical_memory_pin(db_path, cleaned[6:].strip(), pinned=False)
    return await memory_sources_text(db_path, cleaned)


async def _weekly_text(db_path: str, args: str) -> str:
    mode = args.lower().strip()
    if mode in {"status", "runs", "audit"}:
        return await weekly_memory_status_text(db_path)
    if mode in {"run", "now", "start", "save"}:
        return await run_weekly_memory_now_text(db_path, trigger_source="telegram")
    return "weekly reflection"
