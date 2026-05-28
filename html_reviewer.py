from __future__ import annotations

import asyncio
import logging
import os
import re

from cost_tracker import record_usage
from artifact_quality import artifact_skill_context
from models import TheSteward
from provider_capabilities import CAPABILITIES


logger = logging.getLogger(__name__)


async def review_html_app(db_path: str, topic: str, html: str) -> tuple[str, str]:
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.info("Claude HTML review skipped for %r: missing ANTHROPIC_API_KEY", topic)
        return html, "skipped"
    steward = TheSteward(
        os.getenv("ANTHROPIC_API_KEY", "dummy"),
        os.getenv("CLAUDE_STEWARD_MODEL", CAPABILITIES["steward"].default_model),
    )
    try:
        timeout = float(os.getenv("CLAUDE_HTML_REVIEW_TIMEOUT_SECONDS", "35"))
    except ValueError:
        timeout = 35
    try:
        response = await asyncio.wait_for(
            steward.chat([
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": _user_prompt(topic, html)},
            ]),
            timeout=max(10, timeout),
        )
    except Exception as exc:
        logger.warning("Claude HTML review failed for %r: %s", topic, exc)
        return html, "failed"
    reviewed = _clean_html(response)
    if not reviewed:
        logger.warning("Claude HTML review returned non-HTML for %r", topic)
        return html, "rejected"
    await record_usage(db_path, "claude_steward_calls", 1, "html app review")
    return reviewed, "reviewed"


def _system_prompt() -> str:
    return (
        "You are Maya's Claude HTML app reviewer. Kimi or Gemini already wrote the app. "
        "Review and improve the single-file HTML without changing the user's requested purpose. "
        "Fix broken JavaScript, missing accessibility labels, weak mobile layout, unusable controls, "
        "and obvious UX gaps. Do not add external dependencies. Return only the complete HTML file.\n\n"
        f"HTML artifact quality skill:\n{artifact_skill_context('html')}"
    )


def _user_prompt(topic: str, html: str) -> str:
    return (
        f"Topic: {topic}\n\n"
        "Return a complete single-file HTML app. It must keep inline CSS and JavaScript, "
        "include real interactive controls, and avoid prose/specification wrappers.\n\n"
        f"Current HTML:\n{html[:45000]}"
    )


def _clean_html(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:html)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    lowered = cleaned.lower()
    if "<!doctype" not in lowered or "<html" not in lowered:
        return ""
    return cleaned.rstrip() + "\n"
