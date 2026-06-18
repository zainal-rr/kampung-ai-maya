from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable
from uuid import uuid4

import aiosqlite
from telegram import Bot

from maya_core.maya_runtime_config import runtime_config
from maya_core.provenance import provenance_from_source_channel
from maya_core.storage import get_preference
from maya_telegram.telegram_delivery import send_text
from maya_voice.confirmation import (
    CONFIRMATION_TABLE,
    action_fingerprint,
    confirm_action,
    create_pending_confirmation,
    init_confirmation_db,
)


logger = logging.getLogger("maya.meet.approval")
MEET_APPROVAL_SURFACE = "meet_room_action"
TelegramSender = Callable[[str], Awaitable[None]]


@dataclass(frozen=True)
class MeetingApprovalRequest:
    status: str
    spoken: str
    reason_code: str
    action_id: str = ""
    action_fingerprint: str = ""


async def request_meeting_owner_approval(
    db_path: str,
    *,
    request: str,
    action_class: str,
    reason_code: str,
    session_id: str = "",
    content_class: str = "meeting_public",
    telegram_sender: TelegramSender | None = None,
) -> MeetingApprovalRequest:
    payload = {
        "surface": MEET_APPROVAL_SURFACE,
        "request": " ".join(str(request or "").split()),
        "action_class": str(action_class or "unknown_action").strip().lower(),
        "content_class": str(content_class or "meeting_public").strip().lower(),
        "session_id": str(session_id or ""),
        "reason_code": str(reason_code or "meeting_action_requires_owner_approval"),
    }
    action_id = "meet-" + uuid4().hex[:16]
    pending = await create_pending_confirmation(
        db_path,
        action_id=action_id,
        summary=f"Meet request: {payload['request']}",
        payload=payload,
    )
    message = _approval_message(payload, pending)
    try:
        if telegram_sender is not None:
            await telegram_sender(message)
        else:
            await _send_owner_telegram_message(db_path, message)
    except Exception as exc:
        logger.exception("Could not send Meet owner approval to Telegram")
        return MeetingApprovalRequest(
            "needs_confirmation",
            "That needs Zainal's Telegram approval, but I couldn't send the approval request.",
            "telegram_owner_channel_unavailable",
            action_id=pending["action_id"],
            action_fingerprint=pending["action_fingerprint"],
        )
    return MeetingApprovalRequest(
        "needs_confirmation",
        "That needs Zainal's approval. I sent the request to Telegram.",
        "telegram_owner_approval_requested",
        action_id=pending["action_id"],
        action_fingerprint=pending["action_fingerprint"],
    )


async def resolve_meeting_approval_command(db_path: str, text: str, channel: str) -> str | None:
    if str(channel or "").strip().lower() != "telegram":
        return None
    parsed = _parse_approval_command(text)
    if parsed is None:
        return None
    approved, action_id = parsed
    row = await _pending_row(db_path, action_id)
    if row is None:
        return "I could not find that meeting approval request."
    payload = _payload_from_row(row)
    if payload.get("surface") != MEET_APPROVAL_SURFACE:
        return None
    result = await confirm_action(
        db_path,
        action_id=action_id,
        approved=approved,
        action_fingerprint_value=str(row["action_fingerprint"] or ""),
        approver_provenance=provenance_from_source_channel("telegram"),
    )
    if result.get("status") == "approved":
        return "Approved. Maya will run that exact meeting action if the Meet service is still active."
    if result.get("status") == "declined":
        return "Okay, I declined that meeting action."
    return f"I could not approve that meeting action: {result.get('reason_code', 'confirmation_failed')}."


async def claim_approved_meeting_actions(db_path: str, *, limit: int = 5) -> list[dict[str, Any]]:
    await init_confirmation_db(db_path)
    claimed: list[dict[str, Any]] = []
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        rows = await (
            await db.execute(
                f"""
                SELECT * FROM {CONFIRMATION_TABLE}
                WHERE status = 'approved'
                  AND json_extract(payload_json, '$.surface') = ?
                ORDER BY updated_at ASC
                LIMIT ?
                """,
                (MEET_APPROVAL_SURFACE, int(limit)),
            )
        ).fetchall()
        for row in rows:
            payload = _payload_from_row(row)
            if payload.get("surface") != MEET_APPROVAL_SURFACE:
                continue
            if _expired(str(row["expires_at"] or "")):
                await db.execute(
                    f"UPDATE {CONFIRMATION_TABLE} SET status = 'expired', updated_at = CURRENT_TIMESTAMP WHERE action_id = ? AND status = 'approved'",
                    (row["action_id"],),
                )
                continue
            if action_fingerprint(payload) != str(row["action_fingerprint"]):
                await db.execute(
                    f"UPDATE {CONFIRMATION_TABLE} SET status = 'version_conflict', updated_at = CURRENT_TIMESTAMP WHERE action_id = ? AND status = 'approved'",
                    (row["action_id"],),
                )
                continue
            cursor = await db.execute(
                f"UPDATE {CONFIRMATION_TABLE} SET status = 'executing', updated_at = CURRENT_TIMESTAMP WHERE action_id = ? AND status = 'approved'",
                (row["action_id"],),
            )
            if cursor.rowcount != 1:
                continue
            claimed.append({
                "action_id": str(row["action_id"]),
                "action_fingerprint": str(row["action_fingerprint"]),
                "payload": payload,
            })
        await db.commit()
    return claimed


async def mark_meeting_action_execution(db_path: str, action_id: str, *, status: str, detail: str = "") -> None:
    clean_status = status if status in {"executed", "execution_failed"} else "execution_failed"
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            UPDATE {CONFIRMATION_TABLE}
            SET status = ?, summary = CASE WHEN ? != '' THEN ? ELSE summary END, updated_at = CURRENT_TIMESTAMP
            WHERE action_id = ?
            """,
            (clean_status, detail[:1000], detail[:1000], action_id),
        )
        await db.commit()


def _approval_message(payload: dict[str, Any], pending: dict[str, Any]) -> str:
    request = str(payload.get("request") or "meeting action")
    action = str(payload.get("action_class") or "unknown_action")
    reason = str(payload.get("reason_code") or "owner approval required")
    return "\n".join([
        "Maya Meet approval needed",
        f"Action: {request}",
        f"Class: {action}",
        f"Reason: {reason}",
        f"Action ID: {pending['action_id']}",
        f"Fingerprint: {pending['action_fingerprint']}",
        f"Expires: {pending['expires_at']} UTC",
        "",
        f"Reply: approve {pending['action_id']}",
        f"Or: decline {pending['action_id']}",
    ])


async def _send_owner_telegram_message(db_path: str, message: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
    chat_id = (await get_preference(db_path, "telegram_chat_id") or "").strip()
    if not chat_id:
        allowed = runtime_config().telegram_allowed_chat_ids
        chat_id = allowed[0] if allowed else ""
    if not chat_id:
        raise RuntimeError("No Telegram owner chat id is configured")
    await send_text(Bot(token=token), int(chat_id), message)


def _parse_approval_command(text: str) -> tuple[bool, str] | None:
    parts = str(text or "").strip().split()
    if len(parts) != 2:
        return None
    verb, action_id = parts[0].casefold(), parts[1]
    if not action_id.startswith("meet-"):
        return None
    if verb in {"approve", "approved", "yes"}:
        return True, action_id
    if verb in {"decline", "deny", "no"}:
        return False, action_id
    return None


async def _pending_row(db_path: str, action_id: str):
    await init_confirmation_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        return await (
            await db.execute(f"SELECT * FROM {CONFIRMATION_TABLE} WHERE action_id = ?", (action_id,))
        ).fetchone()


def _payload_from_row(row) -> dict[str, Any]:
    try:
        payload = json.loads(str(row["payload_json"] or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _expired(value: str) -> bool:
    try:
        expires_at = datetime.fromisoformat(value.replace("Z", ""))
    except ValueError:
        return True
    return datetime.utcnow() > expires_at
