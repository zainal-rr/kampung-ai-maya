from __future__ import annotations

import os
import re
import asyncio
from dataclasses import dataclass
from urllib.parse import urlparse

from cost_tracker import record_usage
from models import TheHands, TheSenses
from orchestrator_prompts import ARTISAN_SYSTEM_PROMPT
from google import genai
from google.genai import types


@dataclass(frozen=True)
class MarkdownDraft:
    content: str
    grounded: bool = False


async def draft_markdown_with_gemini(db_path: str, topic: str) -> MarkdownDraft | None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    model = os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview")
    prompt = _prompt(topic)
    grounded = should_ground_topic(topic)
    if grounded:
        reply = await _grounded_reply(api_key, model, prompt)
    else:
        senses = TheSenses(api_key, model)
        reply = await senses.chat([
            {"role": "system", "content": "You are Maya's document drafting lane."},
            {"role": "user", "content": prompt},
        ])
    content = _clean_markdown(reply, topic)
    if content:
        await record_usage(db_path, "gemini_flash_text_calls", 1, "markdown draft")
    return MarkdownDraft(content, grounded) if content else None


async def draft_html_with_gemini(db_path: str, topic: str) -> MarkdownDraft | None:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    model = os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview")
    senses = TheSenses(api_key, model)
    reply = await senses.chat([
        {"role": "system", "content": "You are Maya's single-file HTML app builder."},
        {"role": "user", "content": _html_prompt(topic)},
    ])
    content = _clean_html(reply)
    if content:
        await record_usage(db_path, "gemini_flash_text_calls", 1, "html app draft")
    return MarkdownDraft(content, False) if content else None


async def draft_html_with_kimi(db_path: str, topic: str) -> MarkdownDraft | None:
    api_key = os.getenv("KIMI_API_KEY")
    if not api_key:
        return None
    model = html_builder_model()
    hands = TheHands(api_key, model=model)
    try:
        timeout = float(os.getenv("KIMI_HTML_TIMEOUT_SECONDS", "45"))
    except ValueError:
        timeout = 45
    try:
        max_tokens = int(os.getenv("KIMI_HTML_MAX_TOKENS", "3000"))
    except ValueError:
        max_tokens = 3000
    timeout = max(10, timeout)
    try:
        reply = await asyncio.wait_for(
            hands.chat([
                {"role": "system", "content": ARTISAN_SYSTEM_PROMPT},
                {"role": "system", "content": "Build single-file HTML apps. Return only file contents."},
                {"role": "user", "content": _html_prompt(topic)},
            ], max_tokens=max_tokens),
            timeout=timeout,
        )
    except TimeoutError as exc:
        raise TimeoutError(f"{html_builder_lane()} timed out after {timeout:.0f}s") from exc
    content = _clean_html(reply)
    if content:
        await record_usage(db_path, "kimi_coding_calls", 1, "html app draft")
    return MarkdownDraft(content, False) if content else None


def html_builder_model() -> str:
    return os.getenv("KIMI_HTML_MODEL") or os.getenv("KIMI_MODEL", "kimi-k2.6")


def html_builder_lane() -> str:
    model = html_builder_model().lower()
    if model.startswith("moonshot-v1"):
        return "Moonshot V1 HTML app builder"
    return "Kimi HTML app builder"


def should_use_model_draft(topic: str) -> bool:
    return bool(topic.strip())


def should_ground_topic(topic: str) -> bool:
    lowered = topic.lower()
    markers = (
        "new", "latest", "current", "today", "pricing", "price", "released",
        "release", "gemini", "gpt", "claude", "grok", "kimi", "ai model",
        "llm", "compare", "analysis", "research", "news", "meta", "ray-ban",
        "rayban", "smart glasses", "display", "technology",
    )
    return any(marker in lowered for marker in markers)


def _html_prompt(topic: str) -> str:
    return (
        f"Create a complete, usable single-file HTML app for: {topic}\n\n"
        "Return only the file contents. Do not return Markdown. Do not explain the app. "
        "Do not write a specification, plan, checklist, sources section, or prose draft.\n\n"
        "Quality bar:\n"
        "The result should feel like a polished mini app a user can immediately use, not a code sample. "
        "Make concrete product decisions from the topic. Use professional spacing, hierarchy, labels, empty states, "
        "validation messages, and realistic app data where it helps. Avoid generic marketing copy, oversized hero sections, "
        "decorative-only cards, one-note color palettes, and placeholder lorem ipsum.\n\n"
        "Requirements:\n"
        "1) Start with <!DOCTYPE html> and include html, head, body, style, and script tags.\n"
        "2) Build the actual first screen of the app, not a landing page or document.\n"
        "3) Include real interactive controls such as forms, buttons, editable lists, filters, tabs, menus, search, or local storage.\n"
        "4) Use vanilla HTML, CSS, and JavaScript only. No external CDNs or network dependencies.\n"
        "5) Persist user-entered app data in localStorage when useful.\n"
        "6) Keep all CSS and JavaScript inline so the file works offline.\n"
        "7) Make it polished and mobile responsive for phone and desktop.\n"
        "8) Use realistic starter data only when it helps demonstrate the app.\n"
        "9) Include edit/delete or reset behavior when the app manages records.\n"
        "10) Keep text inside buttons and panels short enough to fit on mobile.\n"
        "11) Use valid CSS property names and valid JavaScript. Do not include broken syntax.\n"
    )


async def _grounded_reply(api_key: str, model: str, prompt: str) -> str:
    client = genai.Client(api_key=api_key)
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(tools=[grounding_tool])
    response = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    text = getattr(response, "text", "") or ""
    sources = _sources_from_response(response)
    return _apply_source_quality(text, sources)


def _prompt(topic: str) -> str:
    role = _assumed_role(topic)
    return (
        f"Create a useful working draft about: {topic}\n\n"
        f"Assumed role: {role}\n\n"
        "Write from inside that role. Imagine you are the person or operator who must actually use this document, "
        "spreadsheet, report, note, or slide content in the real world. Make practical assumptions from the topic "
        "when needed, and label those assumptions clearly.\n\n"
        "Rules:\n"
        "1) Use real content, not placeholders.\n"
        "2) Use numbered lists like 1) and a), not dash bullets.\n"
        "3) Touch every key point a real owner would need: goal, assumptions, constraints, steps, risks, costs or resources, timeline, decision points, and next actions.\n"
        "4) Adapt the sections to the artifact type. For spreadsheets, describe useful columns, rows, formulas, statuses, and review fields. For presentations, provide slide-ready sections with strong messages. For Word or Markdown, provide a structured working draft.\n"
        "5) For current products, models, pricing, dates, or releases, prefer official sources first.\n"
        "6) Use these sections when relevant: Role And Assumptions, Working Context, Key Decisions, Plan, Budget Or Resources, Risks, Review Checklist, Next Steps, Officially Verified, Third Party Signals, Needs Verification, Confidence, Sources.\n"
        "7) Do not state exact pricing, release dates, benchmark numbers, or model limits unless tied to a reliable source.\n"
        "8) Clearly separate official facts from third party interpretation.\n"
        "9) Keep it concise but complete enough to become a useful file.\n"
        "10) Include only one Sources section.\n"
        "11) Return only Markdown."
    )


def _assumed_role(topic: str) -> str:
    lowered = topic.lower()
    if any(word in lowered for word in ("travel", "trip", "flight", "hotel", "airbnb", "itinerary", "holiday", "vacation")):
        return "You are the traveller and trip planner who will personally use the plan and budget."
    if any(word in lowered for word in ("drone", "uav", "aerial", "survey", "mapping")):
        return "You run a drone operations company and need this artifact for real client or operations work."
    if any(word in lowered for word in ("budget", "cost", "expense", "spend", "tracker", "spreadsheet", "excel", "xlsx")):
        return "You manage the budget and will maintain this tracker after the file is created."
    if any(word in lowered for word in ("presentation", "pptx", "slides", "deck")):
        return "You are presenting this topic to a practical audience that needs clear decisions and next steps."
    if any(word in lowered for word in ("router", "network", "wifi", "server", "cloud", "system")):
        return "You are the technical owner responsible for setting up, operating, or explaining this system."
    if any(word in lowered for word in ("business", "company", "startup", "client", "proposal")):
        return "You own the business outcome and need this artifact to make a practical decision."
    return "You are the responsible owner of this topic and need a practical working artifact, not a generic summary."


def _clean_markdown(text: str, topic: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("markdown"):
            cleaned = cleaned[len("markdown"):].strip()
    if not cleaned:
        return ""
    if not cleaned.lstrip().startswith("#"):
        cleaned = f"# {topic.strip().title()}\n\n{cleaned}"
    cleaned = _dedupe_sources_sections(cleaned)
    return cleaned.rstrip() + "\n"


def _clean_html(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("html"):
            cleaned = cleaned[4:].strip()
    lowered = cleaned.lower()
    doctype_index = lowered.find("<!doctype")
    if doctype_index < 0 or "<html" not in lowered:
        return ""
    cleaned = cleaned[doctype_index:]
    lowered = cleaned.lower()
    html_end = lowered.rfind("</html>")
    if html_end >= 0:
        cleaned = cleaned[: html_end + len("</html>")]
    return cleaned.rstrip() + "\n"


def _sources_from_response(response) -> list[tuple[str, str]]:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return []
    metadata = getattr(candidates[0], "grounding_metadata", None)
    chunks = getattr(metadata, "grounding_chunks", None) or []
    sources: list[tuple[str, str]] = []
    seen: set[str] = set()
    for chunk in chunks:
        web = getattr(chunk, "web", None)
        uri = getattr(web, "uri", "") if web else ""
        title = getattr(web, "title", "") if web else ""
        if uri and uri not in seen:
            sources.append((title or "Source", uri))
            seen.add(uri)
    return sources[:8]


def _apply_source_quality(text: str, sources: list[tuple[str, str]]) -> str:
    cleaned = _strip_sources_section(_dedupe_sources_sections(text.strip()))
    if not sources:
        return cleaned
    source_block = _source_quality_block(sources)
    return cleaned.rstrip() + "\n\n" + source_block


def _source_quality_block(sources: list[tuple[str, str]]) -> str:
    official: list[tuple[str, str]] = []
    third_party: list[tuple[str, str]] = []
    for title, uri in sources:
        (official if _is_official_source(title, uri) else third_party).append((title, uri))
    lines = ["## Sources"]
    if official:
        lines += ["", "### Official Sources"]
        lines += _numbered_sources(official)
    if third_party:
        lines += ["", "### Third Party Sources"]
        lines += _numbered_sources(third_party)
    if not official:
        lines += ["", "### Confidence Note", "1) No official source was returned by grounding. Treat current claims as needing verification."]
    return "\n".join(lines)


def _numbered_sources(sources: list[tuple[str, str]]) -> list[str]:
    return [f"{idx}) {title or 'Source'}: {uri}" for idx, (title, uri) in enumerate(sources, start=1)]


def _is_official_source(title: str, uri: str) -> bool:
    title_host = title.strip().lower()
    if "." in title_host and not _host_is_official(title_host):
        return False
    host = urlparse(uri).netloc.lower()
    return _host_is_official(host)


def _host_is_official(host: str) -> bool:
    official_hosts = (
        "google.com", "blog.google", "ai.google.dev", "cloud.google.com",
        "developers.google.com", "deepmind.google", "gemini.google.com",
        "google.dev", "meta.com", "ray-ban.com", "about.meta.com",
    )
    return any(host == name or host.endswith("." + name) for name in official_hosts)


def _dedupe_sources_sections(text: str) -> str:
    marker = "\n## Sources"
    first = text.find(marker)
    if first == -1:
        return text
    second = text.find(marker, first + len(marker))
    if second == -1:
        return text
    return text[:second].rstrip()


def _strip_sources_section(text: str) -> str:
    match = re.search(r"\n#{2,3} Sources\b", text)
    if not match:
        return text
    start = match.start()
    next_section = re.search(r"\n#{2,3} (?!Sources\b)", text[match.end():])
    if not next_section:
        return text[:start].rstrip()
    end = match.end() + next_section.start()
    return (text[:start].rstrip() + "\n\n" + text[end:].lstrip()).rstrip()
