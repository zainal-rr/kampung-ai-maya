from __future__ import annotations

from maya_meet.store import meet_session


async def output_session_active(db_path: str, session_id: str) -> bool:
    if not session_id:
        return False
    row = await meet_session(db_path, session_id)
    if not row:
        return False
    status = str(row.get("status") or "").lower()
    terminal = {"ended", "done", "fatal", "failed", "join_failed", "stale", "stopped"}
    if status in terminal:
        return False
    if status.startswith("bot.") and any(marker in status for marker in ("left", "done", "fatal", "ended", "failed")):
        return False
    return True
