from __future__ import annotations

import re


def _section_depth_issues(spec: WordQualitySpec, sections: list[tuple[str, list[str]]]) -> list[str]:
    if not sections:
        return []
    issues: list[str] = []
    section_map: dict[str, list[str]] = {}
    for heading, lines in sections:
        section_map.setdefault(_normalize_heading(heading), []).extend(str(line) for line in lines if str(line).strip())
    skip = {"recipient", "subject"}
    for required in spec.required_headings:
        required_norm = _normalize_heading(required)
        if required_norm in skip:
            continue
        matched_key = ""
        for key in section_map:
            if key == required_norm or key in required_norm or required_norm in key:
                matched_key = key
                break
        if not matched_key:
            continue
        text = " ".join(section_map[matched_key]).strip()
        words = len(text.split())
        threshold = _section_word_threshold(spec, required)
        if words < threshold:
            issues.append(f"{spec.label} section too thin: {required}")
        if _looks_like_meta_section(text):
            issues.append(f"{spec.label} section is generic/meta instead of useful: {required}")
    return issues


def _section_word_threshold(spec: WordQualitySpec, heading: str) -> int:
    heading_norm = _normalize_heading(heading)
    if spec.intent in {"meeting_notes", "letter", "checklist"}:
        return 8
    if heading_norm in {"next steps", "closing", "subject"}:
        return 8
    return spec.min_section_words


def _generic_filler_issues(paragraphs: list[str]) -> list[str]:
    joined = "\n".join(paragraphs).lower()
    markers = (
        "model generated content",
        "generic filler",
        "details go here",
        "add more detail",
        "fill this in",
        "fill in later",
        "to be determined",
        "tbd",
        "insert details",
        "sample text",
    )
    found = [marker for marker in markers if marker in joined]
    if found:
        return ["generic filler text found: " + ", ".join(found[:3])]
    return []


def _looks_like_meta_section(text: str) -> bool:
    lowered = _normalize(text)
    markers = (
        "this section gives",
        "this section includes",
        "for the user's exact request",
        "where relevant",
        "not generic filler",
        "practical decisions constraints examples",
        "the document should",
    )
    return any(marker in lowered for marker in markers)


def _required_match(required: str, headings: tuple[str, ...] | list[str]) -> str:
    required_norm = _normalize_heading(required)
    for heading in headings:
        heading_norm = _normalize_heading(heading)
        if heading_norm == required_norm or required_norm in heading_norm or heading_norm in required_norm:
            return heading
        day = re.match(r"day\s*(\d+)\s*plan", required_norm)
        if day and re.match(rf"day\s*{day.group(1)}\b", heading_norm):
            return heading
    return ""


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def _normalize_heading(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def _title_case_heading(text: str) -> str:
    return " ".join(word[:1].upper() + word[1:] for word in str(text).strip().split())


def _unique_lines(lines: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for line in lines:
        key = _normalize(line)
        if key and key not in seen:
            result.append(line)
            seen.add(key)
    return result
