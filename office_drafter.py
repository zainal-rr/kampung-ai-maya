from __future__ import annotations

import re


def sections_from_markdown(markdown: str, fallback_title: str) -> list[tuple[str, list[str]]]:
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
    return useful[:8] or [("Overview", [f"Draft document about {fallback_title}."])]


def slides_from_markdown(markdown: str, title: str) -> list[tuple[str, list[str]]]:
    sections = sections_from_markdown(markdown, title)
    slides: list[tuple[str, list[str]]] = [(title.title(), ["Draft prepared from grounded Maya notes"])]
    for heading, lines in sections:
        if heading.lower() in {"sources", "official sources", "third party sources"}:
            continue
        slides.append((heading, _limit(lines, 4)))
        if len(slides) >= 7:
            break
    return slides


def spreadsheet_from_markdown(topic: str, markdown: str) -> tuple[list[str], list[list[str]]]:
    if _looks_like_comparison(topic):
        return _comparison_rows(markdown)
    rows: list[list[str]] = []
    for heading, lines in sections_from_markdown(markdown, topic):
        if heading.lower() == "sources":
            continue
        for line in lines[:4]:
            rows.append([heading, line, _confidence_for(heading), "Review"])
    return ["Section", "Detail", "Confidence", "Status"], rows[:30]


def _comparison_rows(markdown: str) -> tuple[list[str], list[list[str]]]:
    rows: list[list[str]] = []
    for heading, lines in sections_from_markdown(markdown, "comparison"):
        if heading.lower() in {"sources", "official sources", "third party sources"}:
            continue
        joined = " ".join(lines[:3])
        rows.append([heading, joined, _confidence_for(heading), "Check source before purchase"])
    return ["Category", "Comparison Notes", "Confidence", "Action"], rows[:25]


def _looks_like_comparison(topic: str) -> bool:
    lowered = topic.lower()
    return "compare" in lowered or "comparison" in lowered or " vs " in lowered or " versus " in lowered


def _heading(line: str) -> str:
    match = re.match(r"^#{1,4}\s+(.+)$", line)
    return _plain(match.group(1)) if match else ""


def _clean_line(line: str) -> str:
    stripped = line.strip()
    if not stripped or stripped.startswith("```"):
        return ""
    stripped = re.sub(r"^\d+\)\s*", "", stripped)
    stripped = re.sub(r"^[a-z]\)\s*", "", stripped, flags=re.IGNORECASE)
    return _plain(stripped)


def _plain(text: str) -> str:
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    return text.strip(" :")


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
