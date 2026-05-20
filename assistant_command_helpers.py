def confirmation_decision(text: str) -> str | None:
    lowered = text.lower().strip().rstrip(".!?")
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


def direct_key(text: str) -> str:
    return text.lower().strip().rstrip("?.! ")


def is_preference_query(query: str) -> bool:
    lowered = query.lower()
    return "preference" in lowered or "prefer" in lowered


def empty_preference_memory_reply(query: str) -> str:
    lowered = query.lower()
    if "telegram" in lowered:
        return "I don't have any Telegram-specific preferences saved yet."
    if "imac" in lowered:
        return "I don't have any iMac-specific preferences saved yet."
    return "I don't have any saved preferences for that yet."


def format_memory_reply(query: str, snippets: list[str], is_preference: bool) -> str:
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
