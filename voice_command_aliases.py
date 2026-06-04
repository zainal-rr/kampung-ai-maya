from __future__ import annotations

import re


_COMMAND_ALIASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("show route", "what route did you use", "what was the last route", "last route"), "/route"),
    (("show status", "what is your status", "maya status", "system status"), "/status"),
    (("show cost", "what did it cost", "how much did it cost", "usage estimate"), "/cost"),
    (("show providers", "provider status", "are your providers ready", "provider readiness"), "/providers"),
    (("show memory", "show memory sources", "what is in your memory", "memory sources"), "/memory"),
    (("show review", "show last review", "what did claude review say", "show artifact review"), "/review"),
    (("show delivery", "show last delivery", "did you send it", "delivery status"), "/delivery"),
    (("show last turn", "show turn", "what happened last turn", "last turn"), "/turn"),
    (("weekly status", "show weekly status", "weekly memory status"), "/weekly status"),
    (("self heal dry run", "show self heal dry run", "selfheal dryrun", "self heal dryrun"), "/selfheal dryrun"),
    (("show artisan", "artisan status", "what did artisan say"), "/artisan"),
)


def spoken_command_alias(text: str, *, channel: str, input_type: str) -> str | None:
    """Return a slash command for natural spoken command phrases.

    These aliases are intentionally narrow. They only activate on iMac/voice
    style inputs so normal Telegram conversation is not over-normalized.
    """
    if channel != "imac" and "voice" not in input_type.lower():
        return None
    normalized = _normalize(text)
    if not normalized:
        return None
    for phrases, command in _COMMAND_ALIASES:
        if normalized in phrases:
            return command
    complex_match = re.match(r"^(?:use complex|complex plan|think deeply about|plan this carefully)\s+(.+)$", normalized)
    if complex_match:
        return "/complex " + complex_match.group(1).strip()
    if normalized.startswith("remember "):
        return "/remember " + normalized.removeprefix("remember ").strip()
    if normalized.startswith("forget "):
        return "/forget " + normalized.removeprefix("forget ").strip()
    complex_request = re.match(r"^this is (?:a )?complex(?: task| project| question)?[:,]?\s*(.+)$", normalized)
    if complex_request:
        return "/complex " + complex_request.group(1).strip()
    if normalized.startswith(("create skill for ", "draft skill for ", "make a skill for ")):
        query = re.sub(r"^(?:create|draft|make)\s+(?:a\s+)?skill\s+for\s+", "", normalized).strip()
        return "/createskill " + query if query else None
    return None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip().rstrip("?.! "))
