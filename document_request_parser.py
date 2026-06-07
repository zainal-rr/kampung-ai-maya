from __future__ import annotations

import re

from document_natural_artifact_parser import (
    artifact_clause_request,
    clean_topic_part,
    natural_artifact_request,
    normalize_artifact_command_text,
    strip_creation_prefix,
)


def document_request(text: str) -> tuple[str, str, bool] | None:
    cleaned = " ".join(text.strip().split()).strip(" .!?")
    cleaned = _repair_leading_command_typo(cleaned)
    cleaned = normalize_artifact_command_text(cleaned)
    if _plain_question_or_explanation(cleaned):
        return None
    misheard_need = _misheard_need_tracker_request(cleaned)
    if misheard_need:
        return misheard_need
    clause = artifact_clause_request(cleaned)
    if clause:
        return clause
    draft = _draft_in_file_request(cleaned)
    if draft:
        return draft
    excel_with_details = re.match(
        r"^(?:create|make|write|give|draft|prepare|generate)\s+(?:me\s+)?(?:an?\s+)?(.+?)\s+"
        r"(?:in|as)\s+(?:an?\s+)?(?:excel|xlsx|spreadsheet|sheet)(?: file| workbook)?\s+with\s+(.+)$",
        cleaned,
        re.IGNORECASE,
    )
    if excel_with_details:
        topic = f"{excel_with_details.group(1).strip()} with {excel_with_details.group(2).strip()}"
        return "xlsx", clean_topic(topic), "this project" in cleaned.lower()
    leading_document = _leading_document_request(cleaned)
    if leading_document:
        return leading_document
    leading_presentation = _leading_presentation_request(cleaned)
    if leading_presentation:
        return leading_presentation
    spreadsheet = _spreadsheet_noun_request(cleaned)
    if spreadsheet:
        return spreadsheet
    deck = _deck_noun_request(cleaned)
    if deck:
        return deck
    implicit_word = _implicit_word_artifact_request(cleaned)
    if implicit_word:
        return implicit_word
    patterns = (
        (r"^(?:create|make|write|give)\s+(?:me\s+)?(?:an?\s+)?(?:md|markdown)(?: file| note)?(?: for this project)?\s+(?:about|on|for)?\s*(.+)$", "md"),
        (r"^(?:create|make|write|give)\s+(?:me\s+)?(?:an?\s+)?(?:html)(?: file| page| app)?(?: for this project)?\s+(?:about|on|for)?\s*(.+)$", "html"),
        (r"^(?:create|make|write|give|draft|prepare|generate)\s+(?:me\s+)?(?:an?\s+)?(.+?)\s+(?:in|as)\s+(?:an?\s+)?(?:md|markdown)(?: file| note)?(?: for this project)?$", "md"),
        (r"^(?:create|make|write|give|draft|prepare|generate)\s+(?:me\s+)?(?:an?\s+)?(.+?)\s+(?:in|as)\s+(?:an?\s+)?(?:html)(?: file| page| app)?(?: for this project)?$", "html"),
        (r"^(?:draft|prepare|generate)\s+(?:me\s+)?(?:an?\s+)?(?:md|markdown)(?: file| note)?(?: for this project)?\s+(?:about|on|for)\s+(.+)$", "md"),
        (r"^(?:create|make|write|give)\s+(?:me\s+)?(?:a\s+)?(?:word doc|word document|work document|docx|doc)(?: for this project)?\s+(?:(?:about|on|for)\s+(?:an?\s+)?)?\s*(.+)$", "docx"),
        (r"^(?:create|make|write|give|draft|prepare|generate)\s+(.+?)\s+(?:in|as)\s+(?:a\s+)?(?:word doc|word document|docx|doc|word|work)(?: for this project)?$", "docx"),
        (r"^(?:create|make|write|give)\s+(?:me\s+)?(?:an?\s+)?(.+?)\s+(?:word doc|word document|work document|docx|doc|word|work)(?: file)?(?: for this project)?(?:\s+(?:about|on|for|to)\s+(.+))?$", "docx"),
        (r"^(?:create|make|write|give)\s+(?:me\s+)?(?:an?\s+)?(?:budgeting\s+|budget\s+|expense\s+)?(?:excel|xlsx|spreadsheet|sheet)(?: file| tracker)?(?: for this project)?\s+(?:about|on|for)?\s*(.+)$", "xlsx"),
        (r"^(?:create|make|write|give|draft|prepare|generate)\s+(?:me\s+)?(?:an?\s+)?(.+?)\s+(?:in|as)\s+(?:an?\s+)?(?:excel|xlsx|spreadsheet|sheet)(?: file| workbook)?(?: for this project)?$", "xlsx"),
        (r"^(?:make|create|craft)\s+(?:me\s+)?(?:an?\s+)?(?:(?:small|quick|short|simple|polished|visual)\s+)*(?:powerpoint|presentation|pptx|slides)(?: file| deck)?\s+(?:on|about|for)\s+(.+)$", "pptx"),
        (r"^(?:create|make|write|give|draft|prepare|generate)\s+(?:me\s+)?(?:an?\s+)?(.+?)\s+(?:in|as)\s+(?:an?\s+)?(?:powerpoint|presentation|pptx|slides)(?: file| deck)?(?: for this project)?$", "pptx"),
    )
    for pattern, kind in patterns:
        match = re.match(pattern, cleaned, re.IGNORECASE)
        if match:
            topic = match.group(1)
            if (match.lastindex or 0) >= 2 and match.group(2):
                topic = f"{topic} for {match.group(2)}"
            return kind, clean_topic(topic), "this project" in cleaned.lower()
    natural = natural_artifact_request(cleaned)
    if natural:
        return natural
    return None


def _repair_leading_command_typo(text: str) -> str:
    lowered = text.lower()
    if lowered.startswith("ake me "):
        return "m" + text
    if lowered.startswith("ake "):
        return "m" + text
    return text


def _misheard_need_tracker_request(cleaned: str) -> tuple[str, str, bool] | None:
    match = re.match(
        r"^in\s+(?:an?\s+)?(.+?\b(?:budget|expense|cost|spending|dining|food|restaurant|restaurants)\s+tracker\b)(?:,?\s+(.+))?$",
        cleaned,
        re.IGNORECASE,
    )
    if not match:
        return None
    detail = re.sub(r"\btoday'?s\b", " ", match.group(2) or "", flags=re.IGNORECASE)
    topic = " ".join(part for part in (match.group(1).strip(), detail.strip()) if part)
    return "xlsx", clean_topic(clean_topic_part(topic)), "this project" in cleaned.lower()


def _plain_question_or_explanation(text: str) -> bool:
    lowered = text.lower().strip()
    starters = (
        "what ",
        "why ",
        "where ",
        "how ",
        "tell me ",
        "explain ",
        "do ",
        "does ",
        "did ",
        "is ",
        "are ",
        "should ",
    )
    return lowered.startswith(starters)


def markdown_update(text: str) -> str | None:
    match = re.match(r"^(?:update|append to|add to)\s+(?:this\s+)?(?:markdown|md)(?: file)?\s+(?:with|about)?\s*(.+)$", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _leading_document_request(cleaned: str) -> tuple[str, str, bool] | None:
    body = strip_creation_prefix(cleaned)
    if not body:
        return None
    match = re.match(
        r"^(?:an?\s+)?(?:word doc|word document|work document|docx|doc|word)(?: file)?"
        r"(?:\s+(?:about|on|for|to)\s+(.+))$",
        body,
        re.IGNORECASE,
    )
    if not match:
        return None
    return "docx", _clean_leading_topic(match.group(1)), "this project" in cleaned.lower()


def _leading_presentation_request(cleaned: str) -> tuple[str, str, bool] | None:
    body = strip_creation_prefix(cleaned)
    if not body:
        return None
    match = re.match(
        r"^(?:an?\s+)?(?:powerpoint|presentation|pptx|slides|deck)(?: file| deck)?"
        r"(?:\s+(?:about|on|for|to)\s+(.+))$",
        body,
        re.IGNORECASE,
    )
    if not match:
        return None
    topic = _clean_leading_topic(match.group(1))
    if body.lower().strip().startswith(("deck", "slides", "pptx")) and "deck" not in topic.lower():
        topic = clean_topic(f"{topic} deck")
    return "pptx", topic, "this project" in cleaned.lower()


def _clean_leading_topic(text: str) -> str:
    cleaned = clean_topic_part(text)
    cleaned = re.sub(r"^(?:about|on|for|to|with)\s+", "", cleaned, flags=re.IGNORECASE)
    return clean_topic(cleaned)


def clean_topic(topic: str) -> str:
    return topic.strip(" .") or "maya-notes"


def _spreadsheet_noun_request(cleaned: str) -> tuple[str, str, bool] | None:
    if re.search(r"\b(?:app|web app|website|html)\b", cleaned, re.IGNORECASE):
        return None
    tracker_in_sheet = re.match(
        r"^(?:create|make|write|give|draft|prepare|generate)\s+(?:me\s+)?(?:an?\s+)?"
        r"(.+?)\s+(?:budget|expense|cost|spending)\s+tracker\s+(?:in|as)\s+(?:an?\s+)?(?:excel|xlsx|spreadsheet|sheet)(?: file| workbook)?(?: for this project)?$",
        cleaned,
        re.IGNORECASE,
    )
    if tracker_in_sheet:
        return "xlsx", clean_topic(f"{tracker_in_sheet.group(1).strip()} budget tracker"), "this project" in cleaned.lower()
    sheet = re.match(
        r"^(?:create|make|write|give|draft|prepare|generate)\s+(?:me\s+)?(?:an?\s+)?"
        r"(.+?)\s+(excel|xlsx|spreadsheet|sheet)(?: file| workbook| budget tracker| tracker)?(?: for this project)?$",
        cleaned,
        re.IGNORECASE,
    )
    if not sheet:
        budget = re.match(
            r"^(?:create|make|write|give|draft|prepare|generate)\s+(?:me\s+)?(?:an?\s+)?"
            r"(.+?)\s+(?:budget|expense|cost|spending)\s+tracker(?: file| workbook)?(?: for this project)?$",
            cleaned,
            re.IGNORECASE,
        )
        if budget:
            return "xlsx", clean_topic(f"{budget.group(1).strip()} budget tracker"), "this project" in cleaned.lower()
        return None
    suffix = " budget tracker" if "tracker" in cleaned.lower() else ""
    topic = re.sub(r"\s+(?:in|as)$", "", sheet.group(1).strip(), flags=re.IGNORECASE)
    return "xlsx", clean_topic(f"{topic}{suffix}"), "this project" in cleaned.lower()


def _deck_noun_request(cleaned: str) -> tuple[str, str, bool] | None:
    match = re.match(
        r"^(?:create|make|write|give|draft|prepare|generate)\s+(?:me\s+)?(?:an?\s+)?"
        r"(.+?)\s+(?:powerpoint\s+deck|presentation\s+deck|slide\s+deck|deck|presentation|slides|pptx)"
        r"(?: file)?(?: for this project)?$",
        cleaned,
        re.IGNORECASE,
    )
    if not match:
        return None
    marker = re.search(r"\b(deck|presentation|slides|pptx)\b", cleaned, re.IGNORECASE)
    label = marker.group(1).lower() if marker else "deck"
    topic_label = "deck" if label in {"deck", "pptx", "slides"} else "presentation"
    return "pptx", clean_topic(f"{match.group(1).strip()} {topic_label}"), "this project" in cleaned.lower()


def _implicit_word_artifact_request(cleaned: str) -> tuple[str, str, bool] | None:
    body = strip_creation_prefix(cleaned)
    if not body:
        return None
    lowered = body.lower()
    if re.search(
        r"\b(?:word|docx|doc|document|excel|xlsx|spreadsheet|sheet|workbook|powerpoint|pptx|slides|deck|"
        r"presentation|markdown|md|html|app|website)\b",
        lowered,
    ):
        return None
    if re.search(r"\b(?:budget|expense|cost|spending)\s+tracker\b", lowered):
        return None
    document_like = re.search(
        r"\b(?:itinerary|travel\s+plan|trip\s+plan|food\s+trip|guide|setup\s+guide|proposal|config|"
        r"configuration|report|brief|research\s+brief|checklist|meeting\s+notes|letter|plan)\b",
        lowered,
    )
    if not document_like:
        return None
    topic = clean_topic(clean_topic_part(body))
    if not topic or topic.lower() in {"plan", "trip plan", "guide", "proposal", "config"}:
        return None
    return "docx", topic, "this project" in cleaned.lower()


def _draft_in_file_request(cleaned: str) -> tuple[str, str, bool] | None:
    match = re.match(
        r"^(?:create|make|write|give|draft|prepare|generate)\s+(?:me\s+)?(?:an?\s+)?(.+?)\s+(?:in|as)\s+(?:an?\s+)?"
        r"(md|markdown|html|word doc|word document|work document|docx|doc|word|work|excel|xlsx|spreadsheet|sheet|powerpoint|presentation|pptx|slides|deck)"
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
    if lowered in {"powerpoint", "presentation", "pptx", "slides", "deck"}:
        return "pptx"
    return "docx"
