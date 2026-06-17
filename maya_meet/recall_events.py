from __future__ import annotations

import json
from typing import Any, Mapping

from maya_meet.recall_security import RecallSignatureError, verify_recall_signature
from maya_meet.store import record_meet_event, update_meet_session


async def handle_recall_event(
    db_path: str,
    *,
    session_id: str,
    secret: str,
    headers: Mapping[str, str],
    raw_payload: str | bytes,
) -> dict[str, str]:
    try:
        verify_recall_signature(secret=secret, headers=headers, payload=raw_payload)
    except RecallSignatureError as exc:
        await record_meet_event(
            db_path,
            session_id=session_id,
            event_type="recall_event_rejected",
            payload={"error": str(exc)},
            accepted=False,
            reason_code=str(exc),
        )
        return {"status": "rejected", "reason_code": str(exc)}
    try:
        payload = json.loads(raw_payload.decode("utf-8") if isinstance(raw_payload, bytes) else raw_payload)
    except json.JSONDecodeError:
        payload = {"raw": str(raw_payload)}
    event_type = str(payload.get("event") or payload.get("type") or "recall_event")
    speaker = _speaker_label(payload)
    await record_meet_event(
        db_path,
        session_id=session_id,
        event_type=event_type,
        payload=payload,
        source_kind="other_speaker",
        speaker_label=speaker,
    )
    if event_type in {"bot.joined", "bot_done", "bot.left", "bot.failed"}:
        await update_meet_session(db_path, session_id, status=event_type, failure_reason=str(payload.get("sub_code") or ""))
    return {"status": "accepted", "reason_code": "verified", "event_type": event_type}


def _speaker_label(payload: dict[str, Any]) -> str:
    participant = payload.get("participant") if isinstance(payload.get("participant"), dict) else {}
    return str(payload.get("speaker") or payload.get("speaker_label") or participant.get("name") or "")
