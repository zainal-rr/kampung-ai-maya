from __future__ import annotations

import re


ACTION_PATTERNS = (
    "book", "buy", "order", "pay", "transfer", "email", "call", "whatsapp",
    "message", "submit", "upload", "download", "install", "uninstall", "update",
    "move", "copy", "rename", "clean", "organize", "renew", "schedule",
    "delete", "remove", "cancel",
)
BARE_CONTROL_WORDS = {"cancel", "stop", "no", "nope", "later"}
SUPPORTED_ACTION_HINTS = (
    "flight", "browser", "chrome", "web", "internet", "project", "folder",
    "file", "markdown", "md", "word document", "docx", "presentation",
    "pptx", "slides", "network", "router",
)
MISSING_SKILL_HINTS = (
    "hotel", "calendar", "shopping", "shop", "account", "login", "design review",
    "security review", "audit security", "figma", "canva", "notion", "email campaign",
)

QUESTION_STARTERS = ("what", "why", "how", "when", "where", "who", "tell me", "explain")
POLITE_PREFIX = r"^(?:maya\s+|please\s+|can you\s+|could you\s+|would you\s+|help me\s+)+"


def unsupported_action_subject(text: str) -> str | None:
    lowered = " ".join(text.lower().strip().split())
    if not lowered or lowered.startswith(QUESTION_STARTERS):
        return None

    candidate = re.sub(POLITE_PREFIX, "", lowered).strip()
    if not candidate:
        return None
    if candidate in BARE_CONTROL_WORDS:
        return None

    if any(hint in candidate for hint in MISSING_SKILL_HINTS):
        return text.strip()
    if any(hint in candidate for hint in SUPPORTED_ACTION_HINTS):
        return None

    if any(candidate.startswith(f"{verb} ") or candidate == verb for verb in ACTION_PATTERNS):
        return text.strip()
    return None
