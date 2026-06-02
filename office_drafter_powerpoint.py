from __future__ import annotations

import re

from office_text_utils import _complete, _plain
from office_drafter_deck_scenarios import _proposal_deck, _technical_deck, _travel_food_deck


def _scenario_powerpoint_slides(title: str, sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    lowered = title.lower()
    if any(word in lowered for word in ("food", "restaurant", "cafe", "trip", "travel", "itinerary")):
        return _travel_food_deck(title, sections)
    if any(word in lowered for word in ("router", "wifi", "wi-fi", "network", "setup", "technical", "config", "configuration", "security", "architecture")):
        return _technical_deck(title, sections)
    if any(word in lowered for word in ("proposal", "business case", "roadmap", "strategy", "quality", "plan")):
        return _proposal_deck(title, sections)
    return []








def _general_powerpoint_slides(title: str, sections: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    display = _display_title(title)
    content_sections = [
        (heading, lines)
        for heading, lines in sections
        if heading.lower() not in {"sources", "official sources", "third party sources"}
    ]
    overview = _take(_all_lines(content_sections), [
        "Use this deck to understand the topic, make a decision, and identify next steps.",
        "The structure moves from context to implications to practical action.",
        "Each slide keeps one message so the presentation stays readable.",
    ])
    slides: list[tuple[str, list[str]]] = [(display, overview)]
    for heading, lines in content_sections[:5]:
        slides.append((_claim_title(heading, lines), _take(lines, [
            f"{heading} is the main point to review.",
            "Clarify the decision or next action tied to this topic.",
            "Use the supporting details as a presenter note, not slide clutter.",
        ])))
    if len(slides) < 5:
        slides.append((
            "The next step is to choose the decision path.",
            [
                "Confirm the goal, owner, and success criteria.",
                "Identify the missing inputs that would change the recommendation.",
                "Turn the deck into an action plan after review.",
            ],
        ))
    return slides


def _clean_slides(slides: list[tuple[str, list[str]]], fallback_title: str) -> list[tuple[str, list[str]]]:
    cleaned: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    for raw_title, raw_bullets in slides:
        title = _clean_slide_title(raw_title) or _display_title(fallback_title)
        key = title.lower()
        if key in seen:
            title = f"{title} ({len(seen) + 1})"
            key = title.lower()
        seen.add(key)
        bullets = [_complete(_plain(str(bullet))) for bullet in raw_bullets if str(bullet).strip()]
        bullets = [bullet for bullet in bullets if not _bad_powerpoint_bullet(bullet)]
        if not bullets:
            bullets = ["Use this slide to make one concrete point."]
        cleaned.append((title, bullets[:3]))
        if len(cleaned) >= 7:
            break
    return cleaned or [(_display_title(fallback_title), ["Use this deck to make the topic clear and actionable."])]


def _display_title(title: str) -> str:
    text = _plain(title)
    text = re.sub(r"\b(powerpoint|pptx|presentation|slide deck|slides|deck)\b", "", text, flags=re.I)
    text = re.sub(r"\b(make|create|draft|about|for|me|a|an|the)\b", "", text, flags=re.I)
    text = " ".join(text.split()).strip(" -:")
    return text.title() if text else title.title()


def _clean_slide_title(title: str) -> str:
    text = _plain(title)
    text = re.sub(r"\s+", " ", text).strip(" .:-")
    if not text:
        return ""
    if len(text) > 92:
        text = text[:92].rsplit(" ", 1)[0]
    if len(text.split()) <= 5 and not re.search(r"\b(is|are|should|needs|need|works|turn|protect|decides|sets)\b", text, re.I):
        return text
    return _complete(text)


def _claim_title(heading: str, lines: list[str]) -> str:
    lowered = heading.lower()
    if any(word in lowered for word in ("overview", "context", "introduction")):
        return "The context sets the decision."
    if any(word in lowered for word in ("recommend", "next")):
        return "The recommendation should be easy to act on."
    if any(word in lowered for word in ("risk", "issue", "constraint")):
        return "The risks need explicit handling."
    if any(word in lowered for word in ("budget", "cost")):
        return "Budget choices need visible tradeoffs."
    if any(word in lowered for word in ("plan", "step", "implementation")):
        return "The plan needs clear sequencing."
    if lines:
        first = _plain(lines[0])
        if 18 <= len(first) <= 90:
            return first
    return f"{heading} should drive the next decision."


def _matching_lines(sections: list[tuple[str, list[str]]], keywords: tuple[str, ...]) -> list[str]:
    matched: list[str] = []
    for heading, lines in sections:
        haystack = f"{heading} {' '.join(lines)}".lower()
        if any(keyword in haystack for keyword in keywords):
            matched.extend(lines)
    return matched


def _all_lines(sections: list[tuple[str, list[str]]]) -> list[str]:
    lines: list[str] = []
    for _, section_lines in sections:
        lines.extend(section_lines)
    return lines


def _take(lines: list[str], fallback: list[str], count: int = 3) -> list[str]:
    chosen = [_complete(_plain(line)) for line in lines if _plain(line)][:count]
    if len(chosen) < count:
        chosen.extend(fallback[: count - len(chosen)])
    return chosen[:count]


def _first(lines: list[str], fallback: str) -> str:
    return _complete(_plain(lines[0])) if lines else fallback


def _bad_powerpoint_bullet(text: str) -> bool:
    lowered = text.lower()
    bad = (
        "draft prepared",
        "model generated content",
        "add a specific point",
        "key concept",
        "supporting detail",
        "placeholder",
    )
    return any(marker in lowered for marker in bad)
