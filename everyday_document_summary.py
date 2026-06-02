from __future__ import annotations

import re
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree

from pptx import Presentation


def _close_workflow_query(text: str) -> str | None:
    match = re.match(r"^(?:pause|close|cancel)\s+(?:the\s+)?(.+?)\s+(?:task|workflow)$", text, re.I)
    return match.group(1).strip(" .") if match else None


def _summary_from_path(path: Path) -> str:
    stem = path.stem.replace("-", " ").replace("_", " ").strip()
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return f"Word document about {stem}."
    if suffix == ".pptx":
        return f"PowerPoint presentation about {stem}."
    if suffix == ".xlsx":
        return f"Excel spreadsheet for {stem}."
    if suffix == ".html":
        return f"HTML file for {stem}."
    return f"File about {stem}."


def _content_summary(path: Path) -> str:
    if not path.exists() or path.suffix.lower() != ".docx":
        return ""
    paragraphs = _docx_paragraphs(path)
    if not paragraphs:
        return ""
    title = paragraphs[0]
    headings = _interesting_headings(paragraphs[1:])
    detail = _first_detail(paragraphs[1:])
    subject = _summary_subject(title)
    sentence = subject
    if headings:
        sentence += " covering " + _friendly_topics(headings[:4])
    if detail:
        sentence += ". " + _friendly_detail(detail)
    return sentence.rstrip(".") + "."


def _pptx_content_summary(path: Path) -> str:
    if not path.exists() or path.suffix.lower() != ".pptx":
        return ""
    try:
        deck = Presentation(path)
    except Exception:
        return ""
    slide_count = len(deck.slides)
    if slide_count <= 0:
        return ""
    titles = [_pptx_slide_title(slide) for slide in deck.slides]
    titles = [title for title in titles if title]
    if not titles:
        return ""
    notes_count = sum(1 for slide in deck.slides if _pptx_slide_notes(slide))
    visible_titles = titles[:6]
    sentence = f"PowerPoint deck with {slide_count} slide{'s' if slide_count != 1 else ''} covering {_join_phrases(visible_titles)}"
    if len(titles) > len(visible_titles):
        sentence += f", and {len(titles) - len(visible_titles)} more"
    if notes_count == slide_count:
        sentence += ". Speaker notes are present on all slides"
    elif notes_count:
        sentence += f". Speaker notes are present on {notes_count} of {slide_count} slides"
    return sentence.rstrip(".") + "."


def _pptx_slide_title(slide) -> str:
    candidates: list[tuple[int, int, str]] = []
    for order, shape in enumerate(slide.shapes):
        text = getattr(shape, "text", "") or ""
        first_line = _clean_pptx_text(text)
        if not first_line:
            continue
        score = _pptx_title_score(first_line)
        if score > 0:
            candidates.append((score, -order, first_line))
    if not candidates:
        return ""
    candidates.sort(reverse=True)
    return candidates[0][2]


def _clean_pptx_text(text: str) -> str:
    lines = [" ".join(line.split()).strip(" .") for line in str(text).splitlines()]
    for line in lines:
        if line:
            return line
    return ""


def _pptx_title_score(text: str) -> int:
    clean = " ".join(str(text).split()).strip()
    if len(clean) < 5:
        return 0
    words = re.findall(r"[A-Za-z0-9]+", clean)
    if not words:
        return 0
    score = 10
    if 2 <= len(words) <= 8:
        score += 8
    if len(words) > 10:
        score -= 6
    if clean.isupper() and len(words) <= 3:
        score -= 8
    if re.search(r"[.!?]$", clean):
        score -= 2
    if "/" in clean and len(words) > 5:
        score -= 4
    if any(word[:1].isupper() for word in words):
        score += 3
    return score


def _pptx_slide_notes(slide) -> str:
    try:
        frame = slide.notes_slide.notes_text_frame
    except Exception:
        return ""
    return " ".join(str(frame.text or "").split()).strip()


def _best_artifact_summary(artifacts: list[dict[str, str]]) -> str:
    if not artifacts:
        return ""
    clean = [
        (
            str(artifact.get("source_tool") or ""),
            str(artifact.get("summary") or "").strip(),
        )
        for artifact in artifacts
    ]
    final_tools = {"document_actions", "direct_document_actions"}
    for source_tool, summary in clean:
        if source_tool in final_tools and _usable_artifact_summary(summary):
            return summary
    for _source_tool, summary in clean:
        if _usable_artifact_summary(summary):
            return summary
    return clean[0][1]


def _usable_artifact_summary(summary: str) -> bool:
    lowered = summary.lower()
    stale_markers = (
        "draft level",
        "draft-level",
        "visual qa still has issues",
        "reject:",
        "rejected",
        "not calling it final",
    )
    return bool(summary.strip()) and not any(marker in lowered for marker in stale_markers)


def _docx_paragraphs(path: Path) -> list[str]:
    try:
        with ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except (KeyError, OSError):
        return []
    root = ElementTree.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace)).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def _interesting_headings(paragraphs: list[str]) -> list[str]:
    generic = {"role and assumptions", "working context", "key decisions", "plan", "next steps"}
    headings = []
    for text in paragraphs:
        lowered = text.lower().strip()
        if lowered in generic:
            headings.append(text)
        elif re.match(r"^(?:day\s+\d+|budget|timeline|itinerary)\b", lowered):
            headings.append(text)
        if len(headings) >= 5:
            break
    return headings


def _first_detail(paragraphs: list[str]) -> str:
    for text in paragraphs:
        lowered = text.lower()
        if lowered.startswith(("role:", "assumption")):
            continue
        if any(marker in lowered for marker in ("kyoto", "tokyo", "trip", "itinerary", "arrival", "departure")):
            return text[:180].rstrip(".")
    return ""


def _join_phrases(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + ", and " + items[-1]


def _summary_subject(title: str) -> str:
    lowered = title.lower()
    day_match = re.match(r"^(?P<count>one|two|three|four|five|six|seven|\d+)\s+days?\s+(?P<place>.+?)\s+trip$", title, re.I)
    if day_match:
        count = day_match.group("count").lower()
        place = day_match.group("place").strip()
        return f"A {count}-day {place} trip plan"
    if "trip" in lowered or "itinerary" in lowered:
        return f"A {title} plan"
    return f"A {title}"


def _friendly_topics(headings: list[str]) -> str:
    cleaned = []
    for heading in headings:
        mapped = _topic_label(heading)
        if mapped:
            cleaned.append(mapped)
            continue
        text = re.sub(r"^Day\s+(\d+):\s*", r"Day \1 ", heading, flags=re.I)
        text = text.replace("&", "and")
        text = re.sub(r"\s*\([^)]*\)", "", text).strip()
        text = re.sub(r"Day\s+(\d+)\s+The\s+", r"Day \1 ", text)
        text = re.sub(r"^Day\s+(\d+)\s+", r"Day \1: ", text)
        cleaned.append(text[0].lower() + text[1:] if text else text)
    return _join_phrases([item for item in cleaned if item])


def _friendly_detail(detail: str) -> str:
    return detail.strip().rstrip(".")


def _topic_label(heading: str) -> str:
    labels = {
        "role and assumptions": "trip assumptions",
        "working context": "travel context",
        "key decisions": "key decisions",
        "plan": "the plan",
        "next steps": "next steps",
    }
    return labels.get(heading.lower().strip(), "")
