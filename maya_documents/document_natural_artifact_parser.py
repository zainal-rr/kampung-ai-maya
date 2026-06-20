from __future__ import annotations

import re


ARTIFACT_NAMES = (
    r"word doc|word document|work document|docx|doc|document|word|work|excel|xlsx|spreadsheet|sheet|"
    r"powerpoint|presentation|pptx|slides|deck|markdown|md|html"
)

ARTIFACT_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("powerpoint deck", "pptx"),
    ("presentation deck", "pptx"),
    ("slide deck", "pptx"),
    ("powerpoint", "pptx"),
    ("presentation", "pptx"),
    ("slides", "pptx"),
    ("pptx", "pptx"),
    ("deck", "pptx"),
    ("budget tracker", "xlsx"),
    ("expense tracker", "xlsx"),
    ("cost tracker", "xlsx"),
    ("spending tracker", "xlsx"),
    ("excel spreadsheet", "xlsx"),
    ("excel workbook", "xlsx"),
    ("excel sheet", "xlsx"),
    ("spreadsheet", "xlsx"),
    ("workbook", "xlsx"),
    ("excel", "xlsx"),
    ("xlsx", "xlsx"),
    ("sheet", "xlsx"),
    ("markdown note", "md"),
    ("markdown file", "md"),
    ("markdown", "md"),
    ("md note", "md"),
    ("md file", "md"),
    ("md", "md"),
    ("html file", "html"),
    ("html page", "html"),
    ("html app", "html"),
    ("html", "html"),
    ("word document", "docx"),
    ("word doc", "docx"),
    ("word file", "docx"),
    ("work document", "docx"),
    ("docx", "docx"),
    ("doc", "docx"),
    ("word", "docx"),
    ("document", "ambiguous"),
)


def normalize_artifact_command_text(text: str) -> str:
    cleaned = " ".join(str(text or "").strip().split()).strip(" .!?")
    for _ in range(4):
        before = cleaned
        cleaned = re.sub(r"^\s*(?:hey|hi|hello)?\s*maya\s*[,:\-]?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(
            r"^\s*(?:um+|uh+|erm+|hmm+|okay\s+wait|ok\s+wait|okay\s+so|ok\s+so|okay|ok|"
            r"sorry|actually|basically|like)\s*[,:\-]?\s*",
            "",
            cleaned,
            flags=re.I,
        )
        if cleaned == before:
            break
    return cleaned.strip(" .!?")


def artifact_clause_request(cleaned: str) -> tuple[str, str, bool] | None:
    cleaned = normalize_artifact_command_text(cleaned)
    patterns = (
        rf"^(.+?)[?.!,;]\s*(?:it|this|that)\s+"
        rf"(?:needs?\s+to\s+be|should\s+be|has\s+to\s+be|must\s+be|is)\s+"
        rf"(?:(?:in|as)\s+)?(?:an?\s+)?({ARTIFACT_NAMES})(?: file| note| workbook| deck)?$",
        rf"^(.+?)[?.!,;]\s*(?:put|save|write|make|keep)\s+(?:it|this|that)\s+"
        rf"(?:in|as)\s+(?:an?\s+)?({ARTIFACT_NAMES})(?: file| note| workbook| deck)?$",
    )
    match = _first_match(patterns, cleaned)
    if not match:
        return None
    lead = strip_creation_prefix(match.group(1).strip()) or match.group(1).strip()
    artifact = match.group(2)
    if artifact.lower() == "document":
        return None
    topic = clean_topic_part(lead)
    if not useful_topic(topic):
        return None
    kind = kind_from_name(artifact)
    if kind == "pptx" and artifact.lower() == "deck" and "deck" not in topic.lower():
        topic = clean_topic_part(f"{topic} deck")
    return kind, clean_topic(topic), "this project" in cleaned.lower()


def natural_artifact_request(cleaned: str) -> tuple[str, str, bool] | None:
    cleaned = normalize_artifact_command_text(cleaned)
    body = strip_creation_prefix(cleaned)
    if not body:
        return None
    artifact = _find_artifact_keyword(body)
    if not artifact:
        return None
    keyword, kind, start, end = artifact
    if keyword.lower() == "document" or kind == "ambiguous":
        return None
    topic = _topic_around_artifact(body, keyword, kind, start, end)
    if not useful_topic(topic):
        return None
    return kind, clean_topic(topic), "this project" in cleaned.lower()


def artifact_intent_clarification(cleaned: str) -> str | None:
    cleaned = normalize_artifact_command_text(cleaned)
    lowered = cleaned.lower().strip()
    body = strip_creation_prefix(cleaned) or cleaned
    if lowered.startswith(("send ", "open ", "show ", "review ", "where ", "what ", "why ", "how ", "tell me ", "explain ")):
        return None
    artifact = _find_artifact_keyword(body)
    if not artifact:
        return None
    keyword, kind, start, end = artifact
    topic = _topic_around_artifact(body, keyword, kind, start, end)
    if not useful_topic(topic):
        return None
    if keyword.lower() == "document" or kind == "ambiguous":
        return (
            f"I understand: {clean_topic(topic)}. Which type should I create: "
            "Word doc, Excel sheet, or PowerPoint slides?"
        )
    if kind == "xlsx":
        return (
            f"I understand: {clean_topic(topic)}. Do you want me to create this as an Excel workbook? "
            "If yes, tell me the days and number of people, or say use the latest trip context."
        )
    if kind == "docx":
        return f"I understand: {clean_topic(topic)}. Do you want me to create this as a Word document?"
    if kind == "pptx":
        return f"I understand: {clean_topic(topic)}. Do you want me to create this as a PowerPoint deck?"
    return f"I understand: {clean_topic(topic)}. Do you want me to create this file?"


def strip_creation_prefix(text: str) -> str:
    patterns = (
        r"^(?:please\s+)?(?:can|could|would)\s+you\s+(?:please\s+)?(?:help\s+me\s+)?(?:make|create|write|draft|prepare|generate|build|put\s+together|put|do)\s+(?:me\s+|my\s+)?",
        r"^(?:please\s+)?(?:help\s+me\s+)?(?:make|create|write|draft|prepare|generate|build|put\s+together|put)\s+(?:me\s+|my\s+)?",
        r"^(?:please\s+)?(?:put\s+together|do)\s+(?:me\s+)?",
        r"^(?:i\s+)?(?:need|want)\s+(?:you\s+to\s+)?(?:(?:make|create|write|draft|prepare|generate|build|put|put\s+together)\s+)?(?:me\s+|my\s+)?",
    )
    match = _first_match(patterns, text)
    return text[match.end() :].strip() if match else ""


def clean_topic(topic: str) -> str:
    return topic.strip(" .") or "maya-notes"


def clean_topic_part(text: str) -> str:
    cleaned = re.sub(r"\bfor\s+this\s+project\b", " ", str(text), flags=re.IGNORECASE)
    cleaned = re.sub(r"\bthis\s+project\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;-")
    cleaned = re.sub(r"^(?:an?|the|my)(?:\s+|$)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:about|on|for|to|in|as|with)\s+(?:an?|the)$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+(?:about|on|for|to|in|as|with)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" .,:;-")


def kind_from_name(name: str) -> str:
    lowered = name.lower()
    if lowered in {"md", "markdown"}:
        return "md"
    if lowered == "html":
        return "html"
    if lowered in {"excel", "xlsx", "spreadsheet", "sheet"}:
        return "xlsx"
    if lowered in {"powerpoint", "presentation", "pptx", "slides", "deck"}:
        return "pptx"
    if lowered == "document":
        return "ambiguous"
    return "docx"


def useful_topic(topic: str) -> bool:
    generic = {
        "document",
        "doc",
        "word",
        "word document",
        "deck",
        "presentation",
        "slides",
        "spreadsheet",
        "excel",
        "sheet",
        "workbook",
        "file",
    }
    words = re.findall(r"[a-z0-9]+", topic.lower())
    return bool(words) and " ".join(words) not in generic


def _first_match(patterns: tuple[str, ...], text: str) -> re.Match[str] | None:
    for pattern in patterns:
        match = re.match(pattern, text, re.IGNORECASE)
        if match:
            return match
    return None


def _find_artifact_keyword(body: str) -> tuple[str, str, int, int] | None:
    matches: list[tuple[str, str, int, int]] = []
    for keyword, kind in ARTIFACT_KEYWORDS:
        for match in re.finditer(rf"\b{re.escape(keyword)}\b", body, re.IGNORECASE):
            matches.append((keyword, kind, match.start(), match.end()))
    if not matches:
        return None
    connector = [item for item in matches if _connector_after(body, item[3])]
    if connector:
        prioritized = _first_by_keyword_priority(connector)
        if prioritized:
            return prioritized
    terminal = [item for item in matches if _terminal_after(body, item[3])]
    if terminal:
        prioritized = _first_by_keyword_priority(terminal)
        if prioritized:
            return prioritized
    for keyword, kind in ARTIFACT_KEYWORDS:
        for item in matches:
            if item[0] == keyword and item[1] == kind:
                return item
    return matches[0]


def _first_by_keyword_priority(matches: list[tuple[str, str, int, int]]) -> tuple[str, str, int, int] | None:
    for keyword, kind in ARTIFACT_KEYWORDS:
        for item in matches:
            if item[0] == keyword and item[1] == kind:
                return item
    return None


def _connector_after(body: str, end: int) -> bool:
    return bool(re.match(r"\s+(?:about|on|for|to|with)\b", body[end:], re.IGNORECASE))


def _terminal_after(body: str, end: int) -> bool:
    return bool(re.match(r"\s*(?:file|note|workbook|deck)?\s*$", body[end:], re.IGNORECASE))


def _topic_around_artifact(body: str, keyword: str, kind: str, start: int, end: int) -> str:
    before = clean_topic_part(body[:start])
    after = clean_topic_part(body[end:])
    if before and after:
        topic = f"{before} {after}"
    else:
        topic = before or _strip_leading_connector(after)
    topic = clean_topic_part(topic)
    if kind == "xlsx" and "tracker" in keyword and "tracker" not in topic.lower():
        topic = clean_topic_part(f"{topic} {keyword}")
    if kind == "pptx" and keyword == "deck" and "deck" not in topic.lower():
        topic = clean_topic_part(f"{topic} deck")
    return topic


def _strip_leading_connector(text: str) -> str:
    return re.sub(r"^(?:about|on|for|to|in|as|with)\s+", "", text, flags=re.IGNORECASE).strip()
