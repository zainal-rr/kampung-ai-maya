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
            event_id=_event_id_from_headers(headers),
            accepted=False,
            reason_code=str(exc),
        )
        return {"status": "rejected", "reason_code": str(exc)}
    try:
        payload = json.loads(raw_payload.decode("utf-8") if isinstance(raw_payload, bytes) else raw_payload)
    except json.JSONDecodeError:
        payload = {"raw": str(raw_payload)}
    event_id = _event_id_from_headers(headers) or _event_id_from_payload(payload)
    event_type = _event_type(payload)
    speaker = _speaker_label(payload)
    inserted = await record_meet_event(
        db_path,
        session_id=session_id,
        event_type=event_type,
        payload=payload,
        event_id=event_id,
        source_kind="other_speaker",
        speaker_label=speaker,
    )
    if not inserted:
        return {"status": "duplicate", "reason_code": "duplicate_recall_event", "event_id": event_id}
    if event_type.startswith("bot."):
        await update_meet_session(
            db_path,
            session_id,
            bot_id=_bot_id(payload),
            status=event_type,
            failure_reason=_sub_code(payload),
        )
    return {"status": "accepted", "reason_code": "verified", "event_type": event_type, "event_id": event_id}


def _speaker_label(payload: dict[str, Any]) -> str:
    participant = payload.get("participant") if isinstance(payload.get("participant"), dict) else {}
    return str(payload.get("speaker") or payload.get("speaker_label") or participant.get("name") or "")


def _event_type(payload: dict[str, Any]) -> str:
    nested = _nested_data(payload)
    return str(payload.get("event") or payload.get("type") or nested.get("code") or "recall_event")


def _bot_id(payload: dict[str, Any]) -> str:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    bot = data.get("bot") if isinstance(data.get("bot"), dict) else {}
    return str(bot.get("id") or payload.get("bot_id") or "")


def _sub_code(payload: dict[str, Any]) -> str:
    nested = _nested_data(payload)
    return str(payload.get("sub_code") or nested.get("sub_code") or "")


def _nested_data(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    nested = data.get("data") if isinstance(data.get("data"), dict) else {}
    return nested


def _event_id_from_headers(headers: Mapping[str, str]) -> str:
    lowered = {str(key).lower(): str(value) for key, value in headers.items()}
    return lowered.get("webhook-id") or lowered.get("svix-id") or ""


def _event_id_from_payload(payload: dict[str, Any]) -> str:
    return str(payload.get("id") or payload.get("event_id") or payload.get("webhook_id") or "")
