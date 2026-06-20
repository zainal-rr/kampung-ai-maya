from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

from maya_core.cost_tracker import record_usage
from maya_core.models import TheNews, TheSenses


MeetingAnswerer = Callable[[str, list[str]], Awaitable[str]]


def build_meeting_context_answerer(db_path: str) -> MeetingAnswerer | None:
    if os.getenv("MAYA_MEET_CONTEXT_MODEL", "1").strip().lower() in {"0", "false", "off", "no"}:
        return None
    xai_key = os.getenv("XAI_API_KEY", "").strip()
    google_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if xai_key:
        model = TheNews(xai_key)
        usage_key = "xai_meet_context_calls"
    elif google_key:
        model = TheSenses(google_key)
        usage_key = "gemini_meet_context_calls"
    else:
        return None

    async def answer(prompt: str, context_lines: list[str]) -> str:
        context = "\n".join(f"- {line}" for line in context_lines[-12:]) or "- No meeting context has been captured yet."
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Maya speaking inside a Google Meet M1 passive proof. "
                    "Answer only from the meeting transcript context below. "
                    "Do not claim private memory, files, browser access, document creation, or commands. "
                    "If the context is insufficient, say that briefly. Keep the spoken answer concise."
                ),
            },
            {
                "role": "user",
                "content": f"Meeting context:\n{context}\n\nQuestion addressed to Maya:\n{prompt}",
            },
        ]
        reply = await model.chat(messages)
        await record_usage(db_path, usage_key, 1, "Meet M1 context answer")
        return reply.strip()

    return answer
