from __future__ import annotations

import os
import re

from maya_core.cost_tracker import record_usage
from maya_core.models import TheSenses


_PRICE_RE = re.compile(r"(?:MYR|RM)\s*[\d,]+", re.I)


def grounded_browser_options(options: list[str], page_text: str, *, limit: int = 5) -> list[str]:
    """Keep only options whose prices and key words actually appear in the page text.

    This guards the Gemini fallback path: an extracted price that is not present
    in the visible page text is treated as hallucinated and dropped.
    """
    if not options or not page_text.strip():
        return []
    page_norm = _normalize_page(page_text)
    return [option for option in options if _is_grounded(str(option), page_norm)][:limit]


def _normalize_page(text: str) -> str:
    cleaned = text.replace("\u00a0", " ").lower()
    return re.sub(r"(?<=\d),(?=\d)", "", cleaned)


def _is_grounded(option: str, page_norm: str) -> bool:
    prices = _PRICE_RE.findall(option)
    if prices:
        for price in prices:
            digits = re.sub(r"\D", "", price)
            if not digits or not re.search(rf"(?<!\d){digits}(?!\d)", page_norm):
                return False
        return True
    tokens = re.findall(r"[a-zA-Z]{5,}", option)[:6]
    if not tokens:
        return False
    hits = sum(1 for token in tokens if token.lower() in page_norm)
    return hits >= max(2, round(len(tokens) * 0.6))


async def extract_browser_options_with_gemini(
    db_path: str,
    *,
    provider: str,
    goal: str,
    page_title: str,
    page_url: str,
    page_text: str,
    limit: int = 5,
) -> list[str]:
    api_key = os.getenv("GOOGLE_API_KEY")
    clean_text = " ".join(page_text.split())
    if not api_key or not clean_text:
        return []
    prompt = [
        {
            "role": "system",
            "content": (
                "You extract travel or browser result options for Maya. "
                "Use only the provided browser page text. Do not invent prices, names, ratings, times, or locations. "
                "Return up to five concise lines. If there are no real options, return exactly NONE."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Provider: {provider}\n"
                f"Goal: {goal}\n"
                f"Title: {page_title}\n"
                f"URL: {page_url}\n"
                f"Page text:\n{clean_text[:12000]}"
            ),
        },
    ]
    reply = (await TheSenses(api_key).chat(prompt)).strip()
    await record_usage(db_path, "gemini_flash_text_calls", 1, f"{provider} browser option extraction")
    if not reply or reply.upper() == "NONE":
        return []
    lines = [line.strip(" -•\t") for line in reply.splitlines() if line.strip(" -•\t")]
    return lines[:limit]
