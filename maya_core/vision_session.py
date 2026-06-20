from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from maya_core.storage import get_preference, upsert_preference
from maya_core.maya_eye_overlay import clear_preview_target
from maya_core.maya_eye_preview import start_preview, stop_preview


SESSION_KEY = "maya_eye_session_until"


async def activate_guided_sight(db_path: str, minutes: int | None = None) -> str:
    duration = minutes or int(os.getenv("MAYA_EYE_SESSION_MINUTES", "10"))
    until = datetime.now(timezone.utc) + timedelta(minutes=duration)
    await upsert_preference(db_path, "work_location", "imac", source="telegram")
    await upsert_preference(db_path, SESSION_KEY, until.isoformat(), source="telegram")
    clear_preview_target()
    preview = start_preview()
    if preview.startswith("I could not") or preview.endswith("disabled."):
        return f"{preview} I am ready for visual help for {duration} minutes."
    return f"I can see now. Ask me what you want me to look at."


async def toggle_guided_sight(db_path: str) -> str:
    if await guided_sight_active(db_path):
        return await deactivate_guided_sight(db_path)
    return await activate_guided_sight(db_path)


async def guided_sight_active(db_path: str) -> bool:
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


async def guided_sight_status(db_path: str) -> str:
    return "on" if await guided_sight_active(db_path) else "off"


async def deactivate_guided_sight(db_path: str, source: str = "telegram") -> str:
    await upsert_preference(db_path, SESSION_KEY, "1970-01-01T00:00:00+00:00", source=source)
    stop_preview()
    return "I stopped seeing."
