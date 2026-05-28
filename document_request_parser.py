from __future__ import annotations

import re


def document_request(text: str) -> tuple[str, str, bool] | None:
    cleaned = " ".join(text.strip().split())
    cleaned = _repair_leading_command_typo(cleaned)
    draft = _draft_in_file_request(cleaned)
    if draft:
        return draft
    patterns = (
        (r"^(?:create|make|write|give)\s+(?:me\s+)?(?:an?\s+)?(?:md|markdown)(?: file| note)?(?: for this project)?\s+(?:about|on|for)?\s*(.+)$", "md"),
        (r"^(?:create|make|write|give)\s+(?:me\s+)?(?:an?\s+)?(?:html)(?: file| page| app)?(?: for this project)?\s+(?:about|on|for)?\s*(.+)$", "html"),
        (r"^(?:draft|prepare|generate)\s+(.+?)\s+(?:in|as)\s+(?:an?\s+)?(?:md|markdown)(?: file| note)?(?: for this project)?$", "md"),
        (r"^(?:draft|prepare|generate)\s+(.+?)\s+(?:in|as)\s+(?:an?\s+)?(?:html)(?: file| page| app)?(?: for this project)?$", "html"),
        (r"^(?:draft|prepare|generate)\s+(?:me\s+)?(?:an?\s+)?(?:md|markdown)(?: file| note)?(?: for this project)?\s+(?:about|on|for)\s+(.+)$", "md"),
        (r"^(?:create|make|write|give)\s+(?:me\s+)?(?:a\s+)?(?:word document|work document|docx|document)(?: for this project)?\s+(?:about|on|for)?\s*(.+)$", "docx"),
        (r"^(?:create|make|write|give)\s+(?:me\s+)?(?:an?\s+)?(.+?)\s+(?:word document|work document|docx|document)(?: for this project)?\s+(?:about|on|for)\s+(.+)$", "docx"),
        (r"^(?:draft|prepare|generate)\s+(.+?)\s+(?:in|as)\s+(?:a\s+)?(?:word document|docx|document)(?: for this project)?$", "docx"),
        (r"^(?:create|make|write|give)\s+(?:me\s+)?(?:an?\s+)?(?:budgeting\s+|budget\s+|expense\s+)?(?:excel|xlsx|spreadsheet|sheet)(?: file| tracker)?(?: for this project)?\s+(?:about|on|for)?\s*(.+)$", "xlsx"),
        (r"^(?:make|create|craft)\s+(?:me\s+)?(?:a\s+)?(?:powerpoint|presentation|pptx|slides)\s+(?:on|about|for)\s+(.+)$", "pptx"),
    )
    for pattern, kind in patterns:
        match = re.match(pattern, cleaned, re.IGNORECASE)
        if match:
            topic = match.group(1)
            if (match.lastindex or 0) >= 2 and match.group(2):
                topic = f"{topic} for {match.group(2)}"
            return kind, clean_topic(topic), "this project" in cleaned.lower()
    return None


def _repair_leading_command_typo(text: str) -> str:
    lowered = text.lower()
    if lowered.startswith("ake me "):
        return "m" + text
    if lowered.startswith("ake "):
        return "m" + text
    return text


def markdown_update(text: str) -> str | None:
    match = re.match(r"^(?:update|append to|add to)\s+(?:this\s+)?(?:markdown|md)(?: file)?\s+(?:with|about)?\s*(.+)$", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def clean_topic(topic: str) -> str:
    return topic.strip(" .") or "maya-notes"


def _draft_in_file_request(cleaned: str) -> tuple[str, str, bool] | None:
    match = re.match(
        r"^(?:draft|prepare|generate)\s+(.+?)\s+(?:in|as)\s+(?:an?\s+)?"
        r"(md|markdown|html|word document|work document|docx|document|excel|xlsx|spreadsheet|sheet|powerpoint|presentation|pptx|slides)"
        r"(?: file| note| tracker)?(?:\s+for\s+(.+))?$",
        cleaned,
        re.IGNORECASE,
    )
    if not match:
        return None
    kind = _kind_from_name(match.group(2))
    scope = (match.group(3) or "").strip()
    project_scoped = "this project" in cleaned.lower()
    topic = match.group(1).strip()
    if scope and "this project" not in scope.lower():
        topic = f"{topic} for {scope}"
    return kind, clean_topic(topic), project_scoped


def _kind_from_name(name: str) -> str:
    lowered = name.lower()
    if lowered in {"md", "markdown"}:
        return "md"
    if lowered == "html":
        return "html"
    if lowered in {"excel", "xlsx", "spreadsheet", "sheet"}:
        return "xlsx"
    if lowered in {"powerpoint", "presentation", "pptx", "slides"}:
        return "pptx"
    return "docx"
