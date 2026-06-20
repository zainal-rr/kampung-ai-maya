from __future__ import annotations

import aiosqlite

from maya_core.provenance import provenance_from_source_channel
from maya_voice.confirmation import action_fingerprint, confirm_action, create_pending_confirmation


def harness_approval_payload(run_id: str, action: str, details: str) -> dict[str, str]:
    return {
        "surface": "harness_approval",
        "run_id": run_id,
        "action": action,
        "details": details[:1000],
    }


def harness_approval_action_id(run_id: str, action: str) -> str:
    return f"harness:{run_id}:{action}"


async def create_harness_confirmation(db_path: str, *, run_id: str, action: str, details: str) -> None:
    await create_pending_confirmation(
        db_path,
        action_id=harness_approval_action_id(run_id, action),
        summary=f"Harness approval: {action}",
        payload=harness_approval_payload(run_id, action, details),
    )


async def confirm_harness_action(db_path: str, *, active: dict, pending: dict, channel: str) -> dict:
    stored = await _stored_pending_approval(db_path, str(active["run_id"]))
    action = str((stored or {}).get("action") or pending.get("action") or "resume_harness_workflow")
    details = str((stored or {}).get("details") or pending.get("details") or "")
    payload = harness_approval_payload(str(active["run_id"]), action, details)
    return await confirm_action(
        db_path,
        action_id=harness_approval_action_id(str(active["run_id"]), action),
        approved=True,
        action_fingerprint_value=action_fingerprint(payload),
        approver_provenance=provenance_from_source_channel(channel),
    )


async def _stored_pending_approval(db_path: str, run_id: str) -> dict[str, str] | None:
    try:
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT action, details
                FROM harness_approvals
                WHERE run_id = ? AND status = 'pending'
                ORDER BY id DESC
                LIMIT 1
                """,
                (run_id,),
            )
            row = await cursor.fetchone()
    except aiosqlite.OperationalError:
        return None
    if not row:
        return None
    return {"action": str(row["action"]), "details": str(row["details"] or "")}
