from __future__ import annotations

from maya_core.assistant_command_helpers import direct_key
from maya_core.briefing_service import BriefingBuilder


WEEKLY_REFLECTION_KEYS = {
    "weekly reflection",
    "show weekly reflection",
    "show my weekly reflection",
    "weekly summary",
    "what did you learn this week",
    "what did you learn about me this week",
}


async def handle_weekly_reflection(db_path: str, text: str, channel: str) -> str | None:
    if direct_key(text) not in WEEKLY_REFLECTION_KEYS:
        return None
    return await BriefingBuilder(db_path).build("weekly_reflection", channel)
