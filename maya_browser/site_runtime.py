from __future__ import annotations

import asyncio

from maya_browser.browser_control import BrowserPage, page_summary
from maya_browser.browser_driver import make_browser_controller


def browser_for(skill):
    if skill.browser is None:
        skill.browser = make_browser_controller(skill.bridge)
    return skill.browser


async def safe_inspect(browser, *, max_chars: int):
    try:
        return await asyncio.to_thread(browser.inspect_page, max_chars)
    except Exception:
        return BrowserPage("", "", "")


async def safe_result_options(browser) -> list[str]:
    try:
        return await asyncio.to_thread(browser.inspect_search_results, 8)
    except Exception:
        return []


def search_reply(spec, query: str, url: str, options: list[str], title: str) -> str:
    lines = [
        f"{spec.name} skill used.",
        f"query: {query}",
        f"url: {url}",
    ]
    if title:
        lines.append(f"title: {title}")
    if options:
        label = "visible results"
        if spec.skill_id == "reddit_research":
            label = "visible community signals"
        elif spec.skill_id == "youtube_research":
            label = "visible videos"
        lines.append(f"{label}:")
        lines.extend(f"{idx}) {item}" for idx, item in enumerate(options[:5], 1))
    else:
        lines.append("visible results: none extracted from page text yet.")
    return "\n".join(lines)
