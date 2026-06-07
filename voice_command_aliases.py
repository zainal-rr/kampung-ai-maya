from __future__ import annotations

import re


_COMMAND_ALIASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("show route", "show me route", "show the route", "show me the route", "what route did you use", "what was the last route", "what was the route", "last route"), "/route"),
    (("status", "show status", "show me status", "show the status", "what is your status", "maya status", "system status"), "/status"),
    (("show cost", "show me cost", "show the cost", "show me the cost", "what did it cost", "how much did it cost", "usage estimate"), "/cost"),
    (("show providers", "show provider status", "show me provider status", "provider status", "are your providers ready", "provider readiness"), "/providers"),
    (("show memory", "show me memory", "show memory sources", "show me memory sources", "what is in your memory", "memory sources"), "/memory"),
    (("show review", "show me review", "show last review", "show me the review", "what did claude review say", "what did the review say", "show artifact review"), "/review"),
    (("show delivery", "show me delivery", "show last delivery", "show me the delivery", "did you send it", "delivery status"), "/delivery"),
    (("show last turn", "show turn", "show me last turn", "show me the last turn", "what happened last turn", "last turn"), "/turn"),
    (("weekly status", "show weekly status", "show me weekly status", "weekly memory status", "show weekly memory status"), "/weekly status"),
    (("self heal dry run", "show self heal dry run", "selfheal dryrun", "self heal dryrun"), "/selfheal dryrun"),
    (("show artisan", "artisan status", "what did artisan say"), "/artisan"),
)


def spoken_command_alias(text: str, *, channel: str, input_type: str) -> str | None:
    """Return a slash command for narrow natural command phrases."""
    normalized = _normalize(text)
    if not normalized:
        return None
    for phrases, command in _COMMAND_ALIASES:
        if normalized in phrases:
            return command
    complex_match = re.match(
        r"^(?:make a complex plan(?: for)?|prepare a checkpointed workflow for|plan an agentic workflow for|complex route|complex task|complex plan|use complex|think deeply about|plan this carefully|complex)[:,]?\s+(.+)$",
        normalized,
    )
    if complex_match:
        return "/complex " + complex_match.group(1).strip()
    if normalized.startswith(("create skill for ", "draft skill for ", "make a skill for ")):
        query = re.sub(r"^(?:create|draft|make)\s+(?:a\s+)?skill\s+for\s+", "", normalized).strip()
        return "/createskill " + query if query else None
    proposed_skill_match = re.match(r"^(?:create|draft|make)\s+(?:a\s+)?proposed\s+skill\s+for\s+(.+)$", normalized)
    if proposed_skill_match:
        query = proposed_skill_match.group(1).strip()
        return "/createskill " + query if query else None
    skill_match = re.match(
        r"^(?:can you\s+)?(?:create|draft|make)\s+(?:a\s+)?(.+?)\s+skill(?:\s+first)?(?:\s+and\s+.+)?$",
        normalized,
    )
    if skill_match:
        query = skill_match.group(1).strip()
        return "/createskill " + query if query else None
    if channel != "imac" and "voice" not in input_type.lower():
        return None
    if normalized.startswith("remember "):
        return "/remember " + normalized.removeprefix("remember ").strip()
    if normalized.startswith("forget "):
        return "/forget " + normalized.removeprefix("forget ").strip()
    complex_request = re.match(r"^this is (?:a )?complex(?: task| project| question)?[:,]?\s*(.+)$", normalized)
    if complex_request:
        return "/complex " + complex_request.group(1).strip()
    return None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip().rstrip("?.! "))
