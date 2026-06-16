from __future__ import annotations

import os

from maya_core.storage import get_preference, upsert_preference

VOICE_KEY = "telegram_voice_replies"


async def voice_enabled(db_path: str) -> bool:
    if os.getenv("TELEGRAM_VOICE_LOCKED", "1") == "1":
        return os.getenv("TELEGRAM_VOICE_REPLIES", "1") == "1"
    return (await get_preference(db_path, VOICE_KEY)) == "1"


async def voice_text(db_path: str, args: str) -> str:
    if os.getenv("TELEGRAM_VOICE_LOCKED", "1") == "1":
        ara_state = "ready" if os.getenv("XAI_API_KEY") else "waiting for XAI_API_KEY"
        return f"Telegram Ara voice replies are locked on. Ara status: {ara_state}."
    mode = args.lower().strip()
    if mode in {"on", "yes", "enable"}:
        await upsert_preference(db_path, VOICE_KEY, "1", source="telegram")
        return "Telegram voice replies are on."
    if mode in {"off", "no", "disable"}:
        await upsert_preference(db_path, VOICE_KEY, "0", source="telegram")
        return "Telegram voice replies are off."
    current = "on" if await voice_enabled(db_path) else "off"
    return f"Telegram voice replies are currently {current}. Use /voice on or /voice off."
