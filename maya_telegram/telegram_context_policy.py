from __future__ import annotations

import re


FULL_CONTEXT_MARKERS = (
    "kampung ai",
    "maya",
    "memory",
    "remember",
    "preference",
    "lesson",
    "project",
    "artifact",
    "document quality",
    "office artifact",
    "last document",
    "latest document",
    "seoul deck",
    "workflow",
    "self heal",
    "self-heal",
)

DIRECT_MEMORY_PATTERNS = (
    r"^what(?:'s| is| was| are)? my\b",
    r"^what do i prefer\b",
    r"^what .+\bdo i prefer\b",
    r"^what did you remember\b",
    r"^do you remember\b",
    r"^tell me my\b",
    r"^show my\b",
)

DOCUMENT_MARKERS = (
    "word",
    "docx",
    "excel",
    "xlsx",
    "spreadsheet",
    "powerpoint",
    "pptx",
    "deck",
    "presentation",
)


def should_use_full_context(
    text: str,
    *,
    channel: str,
    input_type: str = "text",
    complex_route: bool = False,
    sight_route: bool = False,
) -> bool:
    if channel != "telegram":
        return True
    if input_type == "voice note" or complex_route or sight_route:
        return True
    lowered = " ".join(str(text).lower().split())
    if any(marker in lowered for marker in FULL_CONTEXT_MARKERS):
        return True
    if any(marker in lowered for marker in DOCUMENT_MARKERS) and _looks_like_document_action(lowered):
        return True
    return any(re.search(pattern, lowered) for pattern in DIRECT_MEMORY_PATTERNS)


def silent_context_guard(context: str) -> str:
    if not context.strip():
        return ""
    return (
        "Use this support context silently only when it is directly relevant. "
        "Do not quote, list, summarize, or mention the support context, saved facts, "
        "hard facts, preferences, or memory unless the user directly asks about memory/status.\n\n"
        + context
    )


def _looks_like_document_action(lowered: str) -> bool:
    return lowered.startswith((
        "make ",
        "create ",
        "write ",
        "draft ",
        "update ",
        "edit ",
        "send ",
        "open ",
    ))
