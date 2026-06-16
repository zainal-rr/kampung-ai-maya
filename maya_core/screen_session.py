from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from maya_core.storage import get_preference, upsert_preference


SESSION_KEY = "maya_screen_session_until"


async def activate_screen_sight(db_path: str, minutes: int | None = None) -> str:
    duration = minutes or int(os.getenv("MAYA_SCREEN_SESSION_MINUTES", "10080"))
    until = datetime.now(timezone.utc) + timedelta(minutes=duration)
    await upsert_preference(db_path, "work_location", "imac", source="telegram")
    await upsert_preference(db_path, SESSION_KEY, until.isoformat(), source="telegram")
    return "I can see your screen now."


async def toggle_screen_sight(db_path: str) -> str:
    if await screen_sight_active(db_path):
        return await deactivate_screen_sight(db_path)
    return await activate_screen_sight(db_path)


async def screen_sight_active(db_path: str) -> bool:
    raw = await get_preference(db_path, SESSION_KEY)
    if not raw:
        return False
    try:
        until = datetime.fromisoformat(raw)
    except ValueError:
        return False
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return until > datetime.now(timezone.utc)


async def screen_sight_status(db_path: str) -> str:
    return "on" if await screen_sight_active(db_path) else "off"


async def deactivate_screen_sight(db_path: str, source: str = "telegram") -> str:
    await upsert_preference(db_path, SESSION_KEY, "1970-01-01T00:00:00+00:00", source=source)
    return "I stopped looking at your screen."
