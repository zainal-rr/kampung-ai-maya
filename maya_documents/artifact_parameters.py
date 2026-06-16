from __future__ import annotations

import re

from travel_parameters import extract_destination
from word_quality import detect_word_intent
from word_quality_travel import explicit_day_count


def artifact_parameter_question(kind: str, topic: str, channel: str) -> str:
    if kind == "docx":
        return _word_question(topic, channel)
    if kind == "xlsx":
        return _excel_question(topic, channel)
    if kind == "pptx":
        return _pptx_question(topic, channel)
    return ""


def _word_question(topic: str, channel: str) -> str:
    intent = detect_word_intent(topic)
    lowered = _normalize(topic)
    if intent == "travel_itinerary":
        if not _has_destination(lowered):
            return _ask(channel, "Which city or destination should I use for the trip document?")
        if not explicit_day_count(topic) and not _is_short_food_trip(lowered):
            return _ask(channel, "How many days should the trip document cover?")
        return ""
    if intent == "technical_guide" and not _has_specific_subject(lowered):
        return _ask(channel, "What system, product, or workflow should the technical guide cover?")
    if intent == "proposal" and not _proposal_has_object(lowered):
        return _ask(channel, "What is the proposal for, and who is it meant to convince?")
    if intent == "research_brief" and not _research_has_topic(lowered):
        return _ask(channel, "What topic should the research brief cover?")
    if intent == "letter" and not _letter_has_purpose(lowered):
        return _ask(channel, "What should the letter ask for or respond to?")
    return ""


def _excel_question(topic: str, channel: str) -> str:
    lowered = _normalize(topic)
    if _has_any(lowered, ("budget", "tracker", "expense", "cost")) and not _has_subject_after_kind(lowered):
        return _ask(channel, "What should the budget tracker be for?")
    return ""


def _pptx_question(topic: str, channel: str) -> str:
    lowered = _normalize(topic)
    if len(_content_words(lowered)) < 2:
        return _ask(channel, "What topic should the PowerPoint cover?")
    return ""


def _ask(channel: str, question: str) -> str:
    if channel == "imac":
        return question
    return question


def _is_short_food_trip(text: str) -> bool:
    return _has_any(text, ("food trip", "restaurant", "foodie")) and _has_destination(text)


def _has_destination(text: str) -> bool:
    return bool(extract_destination(text))


def _has_specific_subject(text: str) -> bool:
    generic = {"setup", "guide", "technical", "configure", "configuration", "install", "troubleshoot"}
    return len([word for word in _content_words(text) if word not in generic]) >= 1


def _proposal_has_object(text: str) -> bool:
    generic = {"proposal", "doc", "document", "word", "write", "make", "create"}
    return len([word for word in _content_words(text) if word not in generic]) >= 2


def _research_has_topic(text: str) -> bool:
    generic = {"research", "brief", "doc", "document", "word", "about", "make", "create"}
    return len([word for word in _content_words(text) if word not in generic]) >= 1


def _letter_has_purpose(text: str) -> bool:
    purpose = ("refund", "complaint", "request", "resign", "cover", "appeal", "cancel", "cancelled", "canceled")
    return any(word in text for word in purpose)


def _has_subject_after_kind(text: str) -> bool:
    generic = {"budget", "tracker", "expense", "cost", "excel", "xlsx", "sheet", "spreadsheet"}
    return len([word for word in _content_words(text) if word not in generic]) >= 1


def _content_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text)


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()
