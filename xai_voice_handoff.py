from __future__ import annotations

from storage import delete_preference, get_preference, upsert_preference


VOICE_HANDOFF_KEY = "maya_voice_handoff_request"


async def save_voice_handoff_request(db_path: str, request: str) -> None:
    cleaned = " ".join(request.strip().split())
    if cleaned:
        await upsert_preference(db_path, VOICE_HANDOFF_KEY, cleaned, source="voice_handoff")


async def pop_voice_handoff_request(db_path: str) -> str | None:
    request = await get_preference(db_path, VOICE_HANDOFF_KEY)
    if request is not None:
        await delete_preference(db_path, VOICE_HANDOFF_KEY)
    return request
