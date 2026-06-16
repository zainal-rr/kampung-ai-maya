from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from maya_documents.artifact_quality import artifact_skill_context
from maya_core.cost_tracker import record_usage
from models import TheSenses
from word_quality import WORD_DOC_KINDS, normalize_word_doc_kind, word_prompt_context


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArtifactPreflight:
    artifact_type: str
    topic: str
    source: str
    content: str
    cost_recorded: bool = False
    doc_kind: str = "generic_document"

    @property
    def lane_prefix(self) -> str:
        if self.source == "gemini":
            return "Gemini artifact preflight"
        return "local artifact preflight"


async def artifact_preflight_with_gemini(db_path: str, artifact_type: str, topic: str) -> ArtifactPreflight:
    artifact_type = _normalize_type(artifact_type)
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return local_artifact_preflight(artifact_type, topic)
    model = os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview")
    try:
        senses = TheSenses(api_key, model)
        reply = await senses.chat(
            [
                {"role": "system", "content": "You are Maya's artifact preflight role agent."},
                {"role": "user", "content": _preflight_prompt(artifact_type, topic)},
            ]
        )
    except Exception as exc:
        logger.warning("Artifact preflight failed for %s %r: %s", artifact_type, topic, exc)
        fallback = local_artifact_preflight(artifact_type, topic)
        return ArtifactPreflight(
            artifact_type,
            topic,
            "local",
            f"{fallback.content}\n\nPreflight warning: Gemini preflight failed open.",
            False,
            fallback.doc_kind,
        )
    content = _clean_preflight(reply)
    if not content:
        return local_artifact_preflight(artifact_type, topic)
    await record_usage(db_path, "gemini_flash_text_calls", 1, f"artifact preflight {artifact_type}")
    return ArtifactPreflight(artifact_type, topic, "gemini", content, True, _extract_doc_kind(artifact_type, content))


def local_artifact_preflight(artifact_type: str, topic: str) -> ArtifactPreflight:
    artifact_type = _normalize_type(artifact_type)
    if artifact_type == "docx":
        content = _local_word_preflight(topic)
    elif artifact_type == "xlsx":
        content = _local_excel_preflight(topic)
    elif artifact_type == "pptx":
        content = _local_powerpoint_preflight(topic)
    else:
        content = "Intent: create a useful artifact matched to the request.\nQA traps: avoid placeholders, empty sections, and fake completion."
    return ArtifactPreflight(artifact_type, topic, "local", content, False, "generic_document")


def _preflight_prompt(artifact_type: str, topic: str) -> str:
    skill = artifact_skill_context(artifact_type)
    local = local_artifact_preflight(artifact_type, topic).content
    return (
        f"User request: {topic}\n"
        f"Artifact type: {artifact_type}\n\n"
        "Act as a bounded preflight role agent before Maya creates the actual file. "
        "Do not write the file content. Produce a compact blueprint the generator and reviewer can use.\n\n"
        "Return plain text with these labels:\n"
        "Intent:\n"
        "Doc Kind:\n"
        "Audience/Role:\n"
        "Must Include:\n"
        "Useful Assumptions:\n"
        "Quality Traps:\n"
        "Validation Focus:\n"
        "Delivery Summary:\n\n"
        "Rules:\n"
        f"0) For Word Doc Kind, choose only one of: {', '.join(WORD_DOC_KINDS)}. For non-Word artifacts, use generic_document.\n"
        "1) Match the artifact to the user's short intent instead of forcing a long prompt.\n"
        "2) Name scenario-specific sections, sheets, slide arc, formulas, visuals, or evidence needed.\n"
        "3) Identify missing critical parameters only if Maya should ask before creating the file.\n"
        "4) Avoid generic office boilerplate unless the request asks for it.\n"
        "5) For Word, prevent empty headings, placeholders, incomplete frameworks, and malformed markdown.\n"
        "6) For Excel, require useful sheets/columns/formulas/notes and domain-specific rows.\n"
        "7) For PowerPoint, require a clear narrative, readable slides, visual plan, and theme fit.\n"
        "8) Keep the blueprint under 220 words.\n\n"
        f"Local baseline:\n{local}\n\n"
        f"Relevant artifact quality skill:\n{skill[:6000] if skill else '(none loaded)'}"
    )


def _local_word_preflight(topic: str) -> str:
    return (
        "Intent: create a Word document that is useful on first delivery.\n"
        "Doc Kind: generic_document\n"
        "Audience/Role: responsible owner of the topic.\n"
        f"Must Include:\n{word_prompt_context(topic)}\n"
        "Useful Assumptions: make safe practical assumptions when the short request is clear.\n"
        "Quality Traps: no empty headings, no placeholders, no raw markdown dividers, no generic audit sections unless requested, no incomplete tier/step frameworks.\n"
        "Validation Focus: docx opens, headings match the scenario, sections have real content, summary can be extracted.\n"
        "Delivery Summary: state the file name/path and one-line document purpose."
    )


def _local_excel_preflight(topic: str) -> str:
    lowered = topic.lower()
    food = any(word in lowered for word in ("food", "restaurant", "restaurants", "eat", "eating", "foodie"))
    budget = any(word in lowered for word in ("budget", "cost", "expense", "tracker", "spend"))
    lines = [
        "Intent: create an editable Excel workbook that is immediately usable, not a notes dump.",
        "Audience/Role: owner who will keep updating the workbook.",
        "Must Include: meaningful sheet name, useful headers, populated starter rows, frozen headers, pastel styling, sensible widths.",
    ]
    if budget:
        lines.append("Must Include: estimated cost, actual cost, variance, totals, and formulas.")
    if food:
        lines.append("Must Include: per-food or per-restaurant rows, source/restaurant links in notes where available, and suggestions for what to try or prioritize.")
    lines.extend(
        [
            "Useful Assumptions: choose practical starter categories when the user gives a short request.",
            "Quality Traps: no empty workbook, no generic travel template for a specific food-trip tracker, no missing formulas for totals.",
            "Validation Focus: openpyxl load, table-like rows, formulas when implied, useful notes.",
            "Delivery Summary: state workbook purpose, path, and what can be edited.",
        ]
    )
    return "\n".join(lines)


def _local_powerpoint_preflight(topic: str) -> str:
    lowered = topic.lower()
    visual = any(word in lowered for word in ("travel", "food", "product", "pitch", "venue", "place", "city", "app", "design"))
    pastel = any(word in lowered for word in ("pastel", "light theme", "bright theme", "white theme", "not dark", "no dark"))
    theme = "pastel/light theme because the request explicitly asks away from dark" if pastel else "dark/black editorial theme by default"
    image_note = "use Gemini image generation or sourcing where it improves comprehension" if visual else "use visuals only when they clarify the message"
    return (
        "Intent: create an editable PowerPoint deck with a clear narrative arc.\n"
        "Audience/Role: presenter who needs concise slide messages and next steps.\n"
        f"Must Include: design read, one clear idea per slide, strong slide titles, short visible labels, speaker notes for detail, useful structure, {theme}, and {image_note}.\n"
        "Useful Assumptions: choose a compact slide count and organize from context to recommendation.\n"
        "Quality Traps: no generic card-only deck, no repeated weak titles, placeholders, truncated text, unreadable slides, sentence-heavy slide bodies, random decoration, single-image visual-topic deck, or JPEG-only delivery.\n"
        "Validation Focus: pptx opens, render count matches, visual QA passes, text is readable, no overflow, visual topics include multiple relevant images when available.\n"
        "Delivery Summary: state deck purpose, path, and visual QA result."
    )


def _normalize_type(artifact_type: str) -> str:
    lowered = artifact_type.lower().strip(". ")
    aliases = {"word": "docx", "document": "docx", "excel": "xlsx", "spreadsheet": "xlsx", "powerpoint": "pptx", "presentation": "pptx"}
    return aliases.get(lowered, lowered)


def _clean_preflight(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith(("text", "markdown")):
            cleaned = cleaned.split("\n", 1)[1].strip() if "\n" in cleaned else ""
    lines = [line.rstrip() for line in cleaned.splitlines() if line.strip()]
    return "\n".join(lines)[:2500]


def _extract_doc_kind(artifact_type: str, content: str) -> str:
    if _normalize_type(artifact_type) != "docx":
        return "generic_document"
    match = re.search(r"(?im)^\s*Doc Kind\s*:\s*([A-Za-z0-9 _-]+)\s*$", content)
    if not match:
        return "generic_document"
    return normalize_word_doc_kind(match.group(1))
