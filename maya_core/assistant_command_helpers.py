def confirmation_decision(text: str) -> str | None:
    lowered = text.lower().strip().rstrip(".!?")
    if _looks_like_user_request(lowered):
        return None
    approve = {"yes", "y", "yeah", "yep", "sure", "okay", "ok", "go", "go ahead", "do it"}
    decline = {"no", "n", "nope", "cancel", "stop", "no thanks", "no thank you"}
    later = {"later", "not now", "maybe later", "defer"}
    if lowered in approve or lowered.startswith(("yes ", "sure ", "okay ", "ok ", "go ahead")):
        return "approve"
    if lowered in decline or lowered.startswith(("no ", "nope ", "cancel ", "stop ")):
        return "decline"
    if lowered in later or lowered.startswith(("later ", "not now ", "maybe later ")):
        return "later"
    return None


def _looks_like_user_request(text: str) -> bool:
    request_markers = (
        " cakap", " speak", " reply", " write", " create", " make", " give",
        " build", " prepare", " generate", " draft", " put", " need", " want",
        " tell", " buat", " karang", " explain", " summarize", " open", " show",
        " excel", " sheet", " spreadsheet", " workbook", " document", " deck",
        " slides", " powerpoint", " word", " change", " update", " set", " edit",
        " modify", " revise", " switch", " what", " why", " how", " where",
        " do", " does", " did", " is", " are", " should",
    )
    if text in {"okay", "ok", "yes", "sure", "go ahead", "do it"}:
        return False
    return any(marker in f" {text}" for marker in request_markers)


def direct_key(text: str) -> str:
    return text.lower().strip().rstrip("?.! ")


def is_preference_query(query: str) -> bool:
    lowered = query.lower()
    markers = (
        "preference", "prefer", "style", "tone", "voice", "telegram",
        "imac", "communication", "reply", "response", "format",
    )
    return any(marker in lowered for marker in markers)


def empty_preference_memory_reply(query: str) -> str:
    lowered = query.lower()
    if "telegram" in lowered:
        return "I don't have any Telegram-specific preferences saved yet."
    if "imac" in lowered:
        return "I don't have any iMac-specific preferences saved yet."
    return "I don't have any saved preferences for that yet."


def format_memory_reply(query: str, snippets: list[str], is_preference: bool) -> str:
    snippets = filter_user_visible_memory(snippets)
    if not snippets:
        if is_preference:
            return empty_preference_memory_reply(query)
        return "I don't have that saved in memory yet."
    if is_preference:
        scope = preference_scope(query)
        if len(snippets) == 1:
            return f"For {scope}, I have you down for: {snippets[0]}."
        return f"Here's what I have for your {scope}:\n" + "\n".join(f"- {item}" for item in snippets)
    if len(snippets) == 1:
        return f"What I have saved is: {snippets[0]}"
    return "What I have saved:\n" + "\n".join(f"- {item}" for item in snippets)


def preference_scope(query: str) -> str:
    lowered = query.lower()
    if "telegram" in lowered:
        return "Telegram preferences"
    if "imac" in lowered:
        return "iMac preferences"
    return "your preferences"


def filter_user_visible_memory(snippets: list[str]) -> list[str]:
    return [item for item in snippets if is_user_visible_memory(item)]


def is_user_visible_memory(value: str) -> bool:
    lowered = str(value).lower().strip()
    if not lowered:
        return False
    if lowered.startswith("/users/") or "/desktop/maya/" in lowered:
        return False
    file_extensions = (".md", ".docx", ".pptx", ".xlsx", ".svg", ".png", ".jpg", ".jpeg", ".pdf")
    if any(ext in lowered for ext in file_extensions):
        return False
    if lowered == "you are maya, you are the one who see":
        return False
    return True
