"""Semantic artifact intent resolver for messy human requests.

This is the layer that prevents Maya from becoming a pile of regex aliases. It
runs after cheap local command checks but before document builders. The resolver
uses semantic/provider judgment when available to decide whether a message is
normal chat, a request for a concrete artifact, a follow-up edit, or a
clarification case such as "make a document" without saying Word/Excel/PPTX.

Downstream users are `DocumentActionRouter` and the Telegram/iMac channels. The
resolver must not create files itself; it only returns a structured intent so
the artifact router can choose the correct builder, QA loop, delivery channel,
and route/cost record.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from maya_documents.artifact_clarification_state import pending_topic_from_request
from maya_documents.artifact_semantic_enrichment import confidence, infer_domain, merged_parameters, semantic_topic
from maya_core.cost_tracker import record_usage
from maya_core.domain_knowledge import strong_domain_skill_id
from maya_core.models import TheNews


@dataclass(frozen=True)
class SemanticArtifactIntent:
    action: str
    kind: str = ""
    topic: str = ""
    instruction: str = ""
    question: str = ""
    save_copy: bool = False
    domain: str = "unknown"
    parameters: dict[str, object] = field(default_factory=dict)
    confidence: str = "medium"
    original_text: str = ""
    lane: str = ""
    cost_recorded: bool = False


async def resolve_semantic_artifact_intent(db_path: str, text: str) -> SemanticArtifactIntent | None:
    cleaned = " ".join(str(text or "").strip().split()).strip(" .")
    if not _candidate(cleaned):
        return None
    if domain_question_precedence(cleaned):
        # Phase 5 finding 2026-06-12: "design the network for a new branch
        # campus" was hijacked into a Word/Excel/PPT clarification. A message
        # that strongly matches a domain pack and names no explicit artifact
        # format is a QUESTION for the chat lane (where domain retrieval
        # answers it), not an artifact request.
        return None
    ambiguity = _generic_document_question(cleaned)
    if ambiguity:
        return SemanticArtifactIntent("clarify", question=ambiguity, lane="semantic clarification")
    api_key = os.getenv("XAI_API_KEY")
    if os.getenv("MAYA_TEST_MODE") == "1" and os.getenv("MAYA_TEST_ALLOW_SEMANTIC_PROVIDER") != "1":
        return None
    if not api_key:
        return None
    try:
        reply = await TheNews(api_key).chat(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": cleaned},
            ]
        )
        data = _json_object(reply)
    except Exception:
        return None
    intent = _intent_from_data(data, cleaned)
    if not intent:
        return None
    await record_usage(db_path, "grok_text_calls", 1, "semantic artifact router")
    return SemanticArtifactIntent(
        **{**intent.__dict__, "lane": "Grok semantic artifact router", "cost_recorded": True}
    )


_SYSTEM_PROMPT = """Classify a short Maya voice/text request.
Return ONLY JSON:
{"action":"create|edit|clarify|none","kind":"docx|xlsx|pptx|html|md|","domain":"","topic":"","parameters":{},"instruction":"","question":"","save_copy":false,"confidence":"high|medium|low"}

Rules:
1. Use create only when the user wants a real file/artifact.
2. Use edit when the user wants the latest/current file changed.
3. "deck", "slides", or "PowerPoint" means pptx.
4. "Excel", "sheet", "spreadsheet", "workbook", "budget tracker", "cost tracker", or "spending tracker" means xlsx.
5. "Word doc", "Word document", "docx", or "doc" means docx.
6. Bare "document" is ambiguous. Return clarify asking: "Which type should I create: Word doc, Excel sheet, or PowerPoint slides?"
7. Preserve concrete parameters in parameters and topic/instruction: city, days, people/persons/adults/pax, location, destination, formulas, notes, links.
8. Do not promise future work. Only classify.
9. If this is normal chat or an explanation question, action must be none.
10. Domain examples: travel_food_budget, travel_budget, household_budget, business_comparison, technical_guide, proposal, research_brief, presentation, generic_sheet.
"""


# Explicit artifact-format words. A domain-pack question that ALSO names one of
# these still goes to the artifact path ("make an Excel liquidity gap analysis"
# must keep producing a spreadsheet — Phase 4 contract).
_EXPLICIT_FORMAT_MARKERS = (
    "word doc", "word document", "docx", " doc ", "document",
    "excel", "xlsx", "spreadsheet", "workbook", " sheet", "tracker", "ledger",
    "powerpoint", "pptx", "slides", "slide deck", " deck", "presentation",
    "markdown", " md ", "html", "pdf", " file", "save it", "save this", "attach",
    # document-type deliverables (mirror _has_deliverable_signal docx markers):
    "report", "proposal", "guide", "manual", "memo", "letter", " brief",
)


def _explicit_format_marker(lowered: str) -> bool:
    padded = f" {lowered} "
    return any(marker in padded for marker in _EXPLICIT_FORMAT_MARKERS)


def domain_question_precedence(text: str) -> bool:
    """True when the message belongs to a domain pack, not the artifact router.

    Requires BOTH: a strong domain-pack trigger (weak matches never divert) and
    the absence of any explicit artifact-format word. Pure + deterministic so
    the smoke can prove routing without a provider.
    """
    lowered = " ".join(str(text or "").lower().split())
    if not lowered:
        return False
    if _explicit_format_marker(lowered):
        return False
    return bool(strong_domain_skill_id(lowered))


def _candidate(text: str) -> bool:
    lowered = text.lower()
    if not lowered:
        return False
    # This is a cost/noise guard, not an intent classifier. Borderline
    # artifact/edit requests should reach the provider-backed semantic router
    # so voice transcript wording is interpreted by meaning, not local markers.
    if lowered.startswith(("what ", "why ", "how ", "where ", "tell me ", "explain ")):
        return False
    return True


def _generic_document_question(text: str) -> str:
    lowered = text.lower()
    explicit_word = re.search(r"\b(word\s+document|word\s+doc|word\s+file|docx|doc)\b", lowered)
    if explicit_word:
        return ""
    if not re.search(r"\bdocument\b", lowered):
        return ""
    if re.search(r"\b(send|open|show|review|latest|last)\s+(?:me\s+)?(?:the\s+)?(?:latest|last)?\s*document\b", lowered):
        return ""
    if re.search(r"\b(update|edit|change|modify|make)\b", lowered) and re.search(r"\b(this|that|latest|last|the)\s+document\b", lowered):
        return ""
    topic = pending_topic_from_request(text)
    if not topic:
        topic = "that file"
    return f"I understand: {topic}. Which type should I create: Word doc, Excel sheet, or PowerPoint slides?"


def _json_object(text: str) -> dict:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        raw = raw[start : end + 1]
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def _intent_from_data(data: dict, original: str) -> SemanticArtifactIntent | None:
    action = str(data.get("action") or "").strip().lower()
    kind = _normalize_kind(str(data.get("kind") or ""))
    topic = _clean_topic(str(data.get("topic") or ""))
    instruction = _clean_topic(str(data.get("instruction") or ""))
    question = str(data.get("question") or "").strip()
    save_copy = bool(data.get("save_copy"))
    parameters = merged_parameters(original, data.get("parameters"))
    domain = infer_domain(original, kind, topic, parameters, str(data.get("domain") or ""))
    confidence_value = confidence(data.get("confidence"))
    if action == "none":
        return None
    if action == "clarify":
        if not question:
            question = _generic_document_question(original)
        return SemanticArtifactIntent("clarify", question=question, domain=domain, parameters=parameters, confidence=confidence_value, original_text=original) if question else None
    if action == "edit":
        return SemanticArtifactIntent(
            "edit",
            instruction=instruction or original,
            save_copy=save_copy,
            domain=domain,
            parameters=parameters,
            confidence=confidence_value,
            original_text=original,
        )
    if action == "create":
        if kind not in {"docx", "xlsx", "pptx", "html", "md"} or not topic:
            return None
        if not _has_deliverable_signal(original, kind):
            return None
        if kind == "docx" and _generic_document_question(original):
            return SemanticArtifactIntent("clarify", question=_generic_document_question(original))
        topic = semantic_topic(kind, topic, domain, parameters)
        return SemanticArtifactIntent(
            "create",
            kind=kind,
            topic=topic,
            save_copy=save_copy,
            domain=domain,
            parameters=parameters,
            confidence=confidence_value,
            original_text=original,
        )
    return None


def _has_deliverable_signal(text: str, kind: str) -> bool:
    lowered = str(text or "").lower()
    by_kind = {
        "docx": (
            "word",
            "docx",
            "document",
            "doc",
            "guide",
            "proposal",
            "report",
            "brief",
            "letter",
            "manual",
        ),
        "xlsx": (
            "excel",
            "xlsx",
            "sheet",
            "spreadsheet",
            "workbook",
            "budget",
            "cost",
            "spending",
            "expense",
            "tracker",
            "ledger",
        ),
        "pptx": ("powerpoint", "pptx", "slides", "deck", "presentation"),
        "html": ("html", "app", "web page", "website"),
        "md": ("markdown", "md", "note file", "notes file"),
    }
    shared = ("file", "artifact", "save it", "save this", "attach", "send me")
    return any(marker in lowered for marker in (*shared, *by_kind.get(kind, ())))


def _normalize_kind(kind: str) -> str:
    lowered = kind.lower().strip(". ")
    aliases = {
        "word": "docx",
        "document": "docx",
        "doc": "docx",
        "excel": "xlsx",
        "sheet": "xlsx",
        "spreadsheet": "xlsx",
        "workbook": "xlsx",
        "powerpoint": "pptx",
        "presentation": "pptx",
        "slides": "pptx",
        "deck": "pptx",
        "markdown": "md",
    }
    return aliases.get(lowered, lowered)


def _clean_topic(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" .,:;")
    cleaned = re.sub(r"^(?:a|an|the|my)\s+", "", cleaned, flags=re.I)
    return cleaned
