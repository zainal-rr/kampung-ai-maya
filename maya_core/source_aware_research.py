from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Awaitable, Callable
from urllib.parse import urlparse

from maya_core.cost_tracker import record_usage
from google import genai
from google.genai import types
from markdown_drafter import _sources_from_response
from permission_policy import contains_sensitive_info, hard_no_private_exposure_text

ResearchProvider = Callable[[str], Awaitable[tuple[str, list[tuple[str, str]]]]]


@dataclass(frozen=True)
class SourceAwareResearchResult:
    query: str
    answer: str
    sources: tuple[tuple[str, str], ...] = ()
    confidence: str = "low"
    provider_model: str = ""
    grounded: bool = False
    warning: str = ""
    cost_recorded: bool = False


def should_use_source_research(text: str) -> bool:
    lowered = " ".join(str(text).lower().split())
    markers = (
        "research this",
        "research about",
        "do research",
        "find sources",
        "find evidence",
        "give me sources",
        "with sources",
        "with citation",
        "with citations",
        "cite sources",
        "cite this",
        "source-aware",
        "check official",
        "official docs",
        "official source",
        "verify this",
        "is this true",
        "compare sources",
        "look up sources",
        "look this up",
    )
    return any(marker in lowered for marker in markers)


async def source_aware_research(
    db_path: str,
    query: str,
    *,
    memory_context: str = "",
    skill_context: str = "",
    provider: ResearchProvider | None = None,
) -> SourceAwareResearchResult:
    if contains_sensitive_info(query):
        return SourceAwareResearchResult(query, hard_no_private_exposure_text(), warning="sensitive request blocked")
    if provider:
        answer, sources = await provider(_research_prompt(query, memory_context, skill_context))
        return _result(query, answer, sources, model="fake-gemini-grounded", cost=False)
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return SourceAwareResearchResult(query, "Source-aware Gemini research is not available until the Google API key is configured.", warning="missing GOOGLE_API_KEY")
    model = os.getenv("GEMINI_FLASH_MODEL", "gemini-3.1-flash")
    client = genai.Client(api_key=api_key)
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    response = await client.aio.models.generate_content(
        model=model,
        contents=_research_prompt(query, memory_context, skill_context),
        config=types.GenerateContentConfig(tools=[grounding_tool]),
    )
    answer = getattr(response, "text", "") or ""
    sources = _sources_from_response(response)
    await record_usage(db_path, "gemini_flash_text_calls", 1, "source-aware Gemini research")
    return _result(query, answer, sources, model=model, cost=True)


def format_source_research(result: SourceAwareResearchResult, *, channel: str) -> str:
    if not result.sources:
        suffix = f"\n\nSource note: {result.warning or 'Gemini returned no source links, so I am not treating this as verified.'}"
        return _clean_answer(result.answer) + suffix
    lines = [_clean_answer(result.answer), "", "Sources:"]
    for index, (title, uri) in enumerate(result.sources[:5], 1):
        lines.append(f"{index}) {title or 'Source'}: {uri}")
    if result.warning and channel != "imac":
        lines.append(f"\nSource note: {result.warning}")
    return "\n".join(lines).strip()


def _research_prompt(query: str, memory_context: str, skill_context: str) -> str:
    context = "\n\n".join(block for block in (memory_context, skill_context) if block)
    return (
        "Answer with source-aware research. Use official or primary sources first when available. "
        "Do not invent citations. If source links are unavailable, say that clearly. "
        "Keep the answer concise and practical.\n\n"
        f"Context:\n{context or 'No local context.'}\n\n"
        f"Question:\n{query}"
    )


def _result(query: str, answer: str, sources: list[tuple[str, str]], *, model: str, cost: bool) -> SourceAwareResearchResult:
    clean_sources = _dedupe_sources(sources)
    official = [source for source in clean_sources if _official_source(source[1])]
    warning = "" if clean_sources else "No grounded source links were returned."
    if clean_sources and not official:
        warning = "No official source was returned; treat this as lower confidence."
    confidence = "high" if official else ("medium" if clean_sources else "low")
    return SourceAwareResearchResult(
        query,
        answer.strip() or "I could not get a useful grounded answer.",
        tuple(official + [source for source in clean_sources if source not in official])[:5],
        confidence,
        model,
        bool(clean_sources),
        warning,
        cost,
    )


def _dedupe_sources(sources: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[str] = set()
    clean: list[tuple[str, str]] = []
    for title, uri in sources:
        if not uri or uri in seen:
            continue
        seen.add(uri)
        clean.append((title or "Source", uri))
    return clean[:8]


def _official_source(uri: str) -> bool:
    host = urlparse(uri).netloc.lower()
    official_roots = (
        "openai.com",
        "anthropic.com",
        "google.com",
        "ai.google.dev",
        "cloud.google.com",
        "developers.google.com",
        "github.com",
        "python.org",
    )
    return any(host == root or host.endswith("." + root) for root in official_roots)


def _clean_answer(answer: str) -> str:
    text = str(answer).strip()
    marker = text.lower().find("\nsources")
    if marker >= 0:
        text = text[:marker].strip()
    return text or "I could not get a useful grounded answer."
