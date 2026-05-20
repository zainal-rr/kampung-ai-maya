from __future__ import annotations

import os
import re
from collections import Counter

from session_memory_store import latest_session_summary


def quantum_advisory_enabled() -> bool:
    return os.getenv("ENABLE_QUANTUM_ADVISORY", "1") == "1"


async def quantum_context_hint(db_path: str, query: str) -> str:
    if not quantum_advisory_enabled():
        return ""
    if _classical_query(query) or not _intuition_query(query):
        return ""
    summary = await latest_session_summary(db_path)
    if not summary:
        return ""
    summary_text = str(summary["summary"])
    query_terms = _tokens(query)
    if not query_terms:
        return ""
    weighted = _weighted_terms(summary_text, query_terms)
    if not weighted:
        return ""
    related = ", ".join(term for term, _ in weighted[:5])
    score = sum(score for _, score in weighted)
    confidence = "medium" if score >= 3 else "low"
    return (
        "Quantum advisory signal:\n"
        "1) mode: thematic intuition only\n"
        f"2) related terms: {related}\n"
        f"3) confidence: {confidence}\n"
        "4) boundary: use this for how to think, never for what to do next"
    )


def _weighted_terms(summary: str, query_terms: set[str]) -> list[tuple[str, int]]:
    lines = [line.lower() for line in summary.splitlines()]
    counter: Counter[str] = Counter()
    for line in lines:
        line_terms = _tokens(line)
        overlap = len(query_terms & line_terms)
        if overlap:
            if line_terms <= query_terms:
                for term in line_terms:
                    counter[term] += overlap
            for term in line_terms:
                if term not in query_terms:
                    counter[term] += overlap
    return counter.most_common()


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"\b[a-z0-9]{4,}\b", text.lower()) if len(token) > 3}


def _intuition_query(text: str) -> bool:
    lowered = text.lower()
    allowed = (
        "how should i think", "how to think", "think about this", "frame this",
        "framing", "big picture", "theme", "themes", "vibe", "intuition",
        "pattern", "hidden connection", "semantic", "resonance", "high level",
        "summarize at a high level", "what does this mean", "what is the angle",
    )
    return any(phrase in lowered for phrase in allowed)


def _classical_query(text: str) -> bool:
    lowered = text.lower()
    blocked = (
        "what should i do next", "next step", "next steps", "date", "deadline",
        "schedule", "task", "routine", "reminder", "permission",
        "security", "private", "password", "token", "api key", "secret", "bank",
        "payment", "cost", "price", "budget", "invoice", "delete", "send", "share",
        "upload", "booking", "purchase", "passport", "otp",
    )
    return any(word in lowered for word in blocked)
