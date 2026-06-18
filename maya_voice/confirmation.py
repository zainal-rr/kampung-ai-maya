from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any

import aiosqlite

from maya_core.provenance import ProvenanceContext, can_authorize_confirmation, ensure_provenance

CONFIRMATION_TABLE = "voice_pending_confirmations"
DEFAULT_CONFIRMATION_TTL_SECONDS = 120


async def init_confirmation_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {CONFIRMATION_TABLE} (
                action_id TEXT PRIMARY KEY,
                action_fingerprint TEXT NOT NULL,
                summary TEXT DEFAULT '',
                payload_json TEXT DEFAULT '{{}}',
                status TEXT NOT NULL DEFAULT 'pending',
                expires_at DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def create_pending_confirmation(
    db_path: str,
    *,
    action_id: str,
    summary: str,
    payload: dict[str, Any],
    ttl_seconds: int = DEFAULT_CONFIRMATION_TTL_SECONDS,
) -> dict[str, Any]:
    await init_confirmation_db(db_path)
    fingerprint = action_fingerprint(payload)
    expires_at = (datetime.utcnow() + timedelta(seconds=max(1, ttl_seconds))).isoformat(timespec="seconds")
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            INSERT OR REPLACE INTO {CONFIRMATION_TABLE}
                (action_id, action_fingerprint, summary, payload_json, status, expires_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, CURRENT_TIMESTAMP)
            """,
            (action_id, fingerprint, summary[:1000], json.dumps(payload, sort_keys=True), expires_at),
        )
        await db.commit()
    return {"action_id": action_id, "action_fingerprint": fingerprint, "expires_at": expires_at}


async def confirm_action(
    db_path: str,
    *,
    action_id: str,
    approved: bool,
    action_fingerprint_value: str,
    approver_provenance: ProvenanceContext | dict | None = None,
) -> dict[str, Any]:
    await init_confirmation_db(db_path)
    provenance = approver_provenance
    if not can_authorize_confirmation(provenance):
        return {"status": "failed", "reason_code": "unauthorized_confirmation_source"}
    approver = ensure_provenance(provenance, default_kind="unknown")
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(f"SELECT * FROM {CONFIRMATION_TABLE} WHERE action_id = ?", (action_id,))
        row = await cursor.fetchone()
        if not row:
            return {"status": "failed", "reason_code": "confirmation_not_found"}
        if str(row["status"]) != "pending":
            return {"status": "failed", "reason_code": "stale_confirmation"}
        if _expired(str(row["expires_at"] or "")):
            await db.execute(
                f"UPDATE {CONFIRMATION_TABLE} SET status = 'expired', updated_at = CURRENT_TIMESTAMP WHERE action_id = ?",
                (action_id,),
            )
            await db.commit()
            return {"status": "failed", "reason_code": "confirmation_expired"}
        payload = _payload_from_raw(str(row["payload_json"] or "{}"))
        if action_fingerprint(payload) != str(row["action_fingerprint"]):
            return {"status": "failed", "reason_code": "version_conflict"}
        if _meet_room_action_payload(payload) and approver.source_kind != "owner_text":
            return {"status": "failed", "reason_code": "unauthorized_confirmation_source"}
        if action_fingerprint_value != str(row["action_fingerprint"]):
            return {"status": "failed", "reason_code": "version_conflict"}
        status = "approved" if approved else "declined"
        await db.execute(
            f"UPDATE {CONFIRMATION_TABLE} SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE action_id = ?",
            (status, action_id),
        )
        await db.commit()
    return {"status": status, "reason_code": status, "action_id": action_id}


def action_fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _payload_from_raw(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _meet_room_action_payload(payload: dict[str, Any]) -> bool:
    return isinstance(payload, dict) and payload.get("surface") == "meet_room_action"


def _expired(value: str) -> bool:
    try:
        expires_at = datetime.fromisoformat(value.replace("Z", ""))
    except ValueError:
        return True
    return datetime.utcnow() > expires_at
