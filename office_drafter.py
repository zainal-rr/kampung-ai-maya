from __future__ import annotations

import re

from word_quality import canonicalize_word_sections
from office_drafter_powerpoint import _clean_slides, _general_powerpoint_slides, _scenario_powerpoint_slides
from office_text_utils import _plain


def sections_from_markdown(markdown: str, fallback_title: str, limit: int = 8) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_heading = ""
    current_lines: list[str] = []
    for raw in markdown.splitlines():
        line = _clean_line(raw)
        if not line:
            continue
        heading = _heading(line)
        if heading:
            _flush(sections, current_heading, current_lines)
            current_heading, current_lines = heading, []
        elif current_heading:
            current_lines.append(line)
    _flush(sections, current_heading, current_lines)
    useful = [(h, _limit(lines, 6)) for h, lines in sections if lines]
    return useful[:limit] or [("Overview", [f"Draft document about {fallback_title}."])]


def word_sections_from_markdown(markdown: str, topic: str) -> list[tuple[str, list[str]]]:
    return canonicalize_word_sections(topic, sections_from_markdown(markdown, topic, limit=14))


def slides_from_markdown(markdown: str, title: str) -> list[tuple[str, list[str]]]:
    sections = sections_from_markdown(markdown, title)
    scenario = _scenario_powerpoint_slides(title, sections)
    slides = scenario or _general_powerpoint_slides(title, sections)
    return _clean_slides(slides, title)


def spreadsheet_from_markdown(topic: str, markdown: str) -> tuple[list[str], list[list[str]]]:
    if _looks_like_comparison(topic):
        return _comparison_rows(topic, markdown)
    if _looks_like_tracker(topic):
        return _tracker_rows(markdown)
    rows: list[list[str]] = []
    for heading, lines in sections_from_markdown(markdown, topic):
        if heading.lower() == "sources":
            continue
        for line in lines[:4]:
            rows.append([heading, line, _confidence_for(heading), "Review"])
    return ["Section", "Detail", "Confidence", "Status", "Next Action"], [row + ["Review or refine"] for row in rows[:30]]


def _comparison_rows(topic: str, markdown: str) -> tuple[list[str], list[list[str]]]:
    option_a, option_b = _comparison_options(topic)
    rows: list[list[str]] = []
    for heading, lines in sections_from_markdown(markdown, "comparison"):
        if heading.lower() in {"sources", "official sources", "third party sources"}:
            continue
        joined = " ".join(lines[:3])
        rows.append([heading, joined, "", _confidence_for(heading), "Check source before purchase"])
    if len(rows) < 4:
        rows.extend([
            ["Cost", "", "", "Medium", "Estimate setup and maintenance cost"],
            ["Setup Effort", "", "", "Medium", "Compare installation steps and required hardware"],
            ["Reliability", "", "", "Medium", "Check coverage, failure modes, and support burden"],
            ["Recommendation", "", "", "Medium", "Choose based on the actual site constraint"],
        ])
    return ["Criteria", option_a, option_b, "Confidence", "Action"], rows[:25]


def _tracker_rows(markdown: str) -> tuple[list[str], list[list[str]]]:
    rows: list[list[str]] = []
    for heading, lines in sections_from_markdown(markdown, "tracker"):
        if heading.lower() == "sources":
            continue
        for line in lines[:4]:
            rows.append([heading, line, "Not started", "Medium", "", ""])
    if not rows:
        rows = [["Item", "Add the first item", "Not started", "Medium", "", ""]]
    return ["Group", "Item", "Status", "Priority", "Due Date", "Notes"], rows[:30]


def _looks_like_comparison(topic: str) -> bool:
    lowered = topic.lower()
    return "compare" in lowered or "comparison" in lowered or " vs " in lowered or " versus " in lowered


def _looks_like_tracker(topic: str) -> bool:
    lowered = topic.lower()
    return "tracker" in lowered or "tracking" in lowered or "kanban" in lowered


def _comparison_options(topic: str) -> tuple[str, str]:
    match = re.search(r"\bfor\s+(.+?)\s+and\s+(.+?)(?:\s+in\s+|\s+with\s+|$)", topic, re.I)
    if not match:
        match = re.search(r"\bcompare\s+(.+?)\s+(?:and|vs|versus)\s+(.+?)(?:\s+in\s+|\s+with\s+|$)", topic, re.I)
    if not match:
        return "Option A", "Option B"
    return _plain(match.group(1)).title()[:30] or "Option A", _plain(match.group(2)).title()[:30] or "Option B"


def _heading(line: str) -> str:
    match = re.match(r"^#{1,4}\s+(.+)$", line)
    return _plain(match.group(1)) if match else ""


def _clean_line(line: str) -> str:
    stripped = line.strip()
    if not stripped or stripped.startswith("```"):
        return ""
    stripped = re.sub(r"^[-*]\s*", "", stripped)
    stripped = re.sub(r"^\d+\)\s*", "", stripped)
    stripped = re.sub(r"^[a-z]\)\s*", "", stripped, flags=re.IGNORECASE)
    return _plain(stripped)






def _flush(sections: list[tuple[str, list[str]]], heading: str, lines: list[str]) -> None:
    if heading and lines:
        sections.append((heading, lines.copy()))


def _limit(lines: list[str], count: int) -> list[str]:
    return [line for line in lines if line][:count]


def _confidence_for(heading: str) -> str:
    lowered = heading.lower()
    if "official" in lowered:
        return "High"
    if "verification" in lowered or "risk" in lowered:
        return "Needs review"
    if "third party" in lowered:
        return "Medium"
    return "Draft"
