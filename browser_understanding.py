from __future__ import annotations

import os

from cost_tracker import record_usage
from models import TheSenses


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
