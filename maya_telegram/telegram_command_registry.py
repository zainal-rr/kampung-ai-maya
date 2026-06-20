from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TelegramCommandSpec:
    name: str
    summary: str
    usage: str
    registered: bool = False


REGISTERED_COMMANDS = (
    TelegramCommandSpec("help", "Show the full command map", "/help", True),
    TelegramCommandSpec("status", "Show Maya runtime status", "/status", True),
    TelegramCommandSpec("imac", "Switch iMac mode", "/imac on|off", True),
    TelegramCommandSpec("see", "Toggle camera guidance", "/see", True),
    TelegramCommandSpec("screen", "Toggle or ask about screen awareness", "/screen [question]", True),
    TelegramCommandSpec("project", "Show or close active project", "/project [close]", True),
    TelegramCommandSpec("memory", "Show or manage memory", "/memory [subcommand]", True),
    TelegramCommandSpec("join", "Send Maya into a Google Meet", "/join <meet-url>", True),
    TelegramCommandSpec("leave", "Remove Maya from the current Meet", "/leave [meet-url]", True),
    TelegramCommandSpec("meetstatus", "Show Meet status from source-of-truth", "/meetstatus [meet-url]", True),
    TelegramCommandSpec("reliability", "Show scorecard or log a note", "/reliability [note category text]", True),
    TelegramCommandSpec("error", "Record failure evidence and start fresh", "/error [category] <what failed>", True),
    TelegramCommandSpec("complex", "Use the complex reasoning lane", "/complex <request>", True),
)

HIDDEN_COMMANDS = (
    TelegramCommandSpec("openimac", "Alias for iMac on", "/openimac"),
    TelegramCommandSpec("closeimac", "Alias for iMac off", "/closeimac"),
    TelegramCommandSpec("remember", "Save an owner-authored note", "/remember <note>"),
    TelegramCommandSpec("voice", "Show or set Telegram voice status", "/voice [on|off]"),
    TelegramCommandSpec("tasks", "Show open tasks", "/tasks"),
    TelegramCommandSpec("routines", "Show routines", "/routines"),
    TelegramCommandSpec("preferences", "Show saved preferences", "/preferences"),
    TelegramCommandSpec("forget", "Forget a memory", "/forget <target>"),
    TelegramCommandSpec("memorycleanup", "Clean stale memory", "/memorycleanup"),
    TelegramCommandSpec("memorymigrate", "Run canonical memory migration", "/memorymigrate"),
    TelegramCommandSpec("memoryinspect", "Inspect canonical memory", "/memoryinspect [target]"),
    TelegramCommandSpec("memorypin", "Pin canonical memory", "/memorypin <target>"),
    TelegramCommandSpec("memoryunpin", "Unpin canonical memory", "/memoryunpin <target>"),
    TelegramCommandSpec("lessons", "Show recent lessons", "/lessons"),
    TelegramCommandSpec("skills", "Show available skills", "/skills"),
    TelegramCommandSpec("createskill", "Draft a skill proposal", "/createskill <idea>"),
    TelegramCommandSpec("proposals", "Show skill proposals", "/proposals"),
    TelegramCommandSpec("cost", "Show usage estimate", "/cost"),
    TelegramCommandSpec("providers", "Show provider readiness", "/providers"),
    TelegramCommandSpec("route", "Show last routing decision", "/route"),
    TelegramCommandSpec("delivery", "Show last Telegram delivery", "/delivery"),
    TelegramCommandSpec("lastdelivery", "Alias for delivery", "/lastdelivery"),
    TelegramCommandSpec("turn", "Show last Telegram turn", "/turn"),
    TelegramCommandSpec("lastturn", "Alias for turn", "/lastturn"),
    TelegramCommandSpec("review", "Show or resolve latest artifact QA", "/review [resolution]"),
    TelegramCommandSpec("artifactreview", "Alias for artifact QA", "/artifactreview"),
    TelegramCommandSpec("artifactqa", "Alias for artifact QA", "/artifactqa"),
    TelegramCommandSpec("context", "Show compacted context window", "/context"),
    TelegramCommandSpec("weekly", "Show or run weekly memory reflection", "/weekly [status|run]"),
    TelegramCommandSpec("newtopic", "Start a fresh topic", "/newtopic"),
    TelegramCommandSpec("selfheal", "Run safe self-heal check", "/selfheal [dryrun|force]"),
    TelegramCommandSpec("artisan", "Show or apply Artisan output", "/artisan [transcript|app|maker|apply]"),
)

SUBCOMMAND_NOTES = (
    "/memory: preferences, lessons, forget <target>, cleanup, migrate, inspect [target], pin <target>, unpin <target>",
    "/reliability note: categories correction, missed_reply, route, voice, memory, delivery, browser, cost, false_done",
    "/error: same categories as reliability note; records evidence snapshot and opens a fresh topic",
    "/weekly: status, run",
    "/artisan: transcript, app, maker, apply",
)


def registered_command_specs() -> tuple[TelegramCommandSpec, ...]:
    return REGISTERED_COMMANDS


def hidden_command_specs() -> tuple[TelegramCommandSpec, ...]:
    return HIDDEN_COMMANDS


def all_command_specs() -> tuple[TelegramCommandSpec, ...]:
    return REGISTERED_COMMANDS + HIDDEN_COMMANDS


def all_command_names() -> tuple[str, ...]:
    return tuple(spec.name for spec in all_command_specs())


def command_help_text() -> str:
    lines = ["Maya commands:", "1) Registered menu commands"]
    lines.extend(_spec_lines(REGISTERED_COMMANDS))
    lines.append("2) Hidden slash commands")
    lines.extend(_spec_lines(HIDDEN_COMMANDS))
    lines.append("3) Subcommands and categories")
    lines.extend(f"- {note}" for note in SUBCOMMAND_NOTES)
    lines.append("Normal language still works: open project Kampung AI, show my tasks, remember my preference.")
    return "\n".join(lines)


def _spec_lines(specs: tuple[TelegramCommandSpec, ...]) -> list[str]:
    return [f"- {spec.usage}: {spec.summary}" for spec in specs]
