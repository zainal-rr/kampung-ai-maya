from __future__ import annotations

import json

from maya_core.provenance import provenance_from_source_channel
from maya_core.storage import get_preference, upsert_preference
from maya_voice.confirmation import action_fingerprint, confirm_action, create_pending_confirmation

PENDING_CLICK_KEY = "maya_pending_browser_click"


def browser_click_payload(target: str, browser_state: dict | None = None) -> dict[str, str]:
    state = browser_state or {}
    return {
        "surface": "browser_click",
        "target": str(target),
        "current_url": str(state.get("current_url") or ""),
        "page_title": str(state.get("page_title") or ""),
        "last_observation_id": str(state.get("last_observation_id") or ""),
        "task_type": str(state.get("task_type") or ""),
    }


async def remember_pending_click(db_path: str, target: str, browser_state: dict | None = None) -> dict[str, str]:
    payload = browser_click_payload(target, browser_state)
    fingerprint = action_fingerprint(payload)
    action_id = f"browser_click:{fingerprint[:24]}"
    pending = {"target": target, "action_id": action_id, "action_fingerprint": fingerprint}
    await create_pending_confirmation(db_path, action_id=action_id, summary=f"Click {target} in Chrome", payload=payload)
    await upsert_preference(db_path, PENDING_CLICK_KEY, json.dumps(pending, sort_keys=True), source="workflow")
    return pending


async def pending_click_from_store(db_path: str) -> dict[str, str] | None:
    raw = await get_preference(db_path, PENDING_CLICK_KEY)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        target = raw
        payload = browser_click_payload(target)
        fingerprint = action_fingerprint(payload)
        action_id = f"browser_click:{fingerprint[:24]}"
        return {"target": target, "action_id": action_id, "action_fingerprint": fingerprint}
    if not isinstance(data, dict) or not data.get("target"):
        return None
    return {
        "target": str(data["target"]),
        "action_id": str(data.get("action_id") or ""),
        "action_fingerprint": str(data.get("action_fingerprint") or ""),
    }


async def confirm_pending_click(
    db_path: str,
    *,
    channel: str,
    browser_state: dict | None = None,
) -> tuple[dict, dict[str, str] | None]:
    pending = await pending_click_from_store(db_path)
    if not pending:
        return {"status": "failed", "reason_code": "confirmation_not_found"}, None
    if browser_state is not None:
        current_fingerprint = action_fingerprint(browser_click_payload(str(pending["target"]), browser_state))
        if current_fingerprint != str(pending["action_fingerprint"]):
            return {"status": "failed", "reason_code": "version_conflict"}, pending
    result = await confirm_action(
        db_path,
        action_id=str(pending["action_id"]),
        approved=True,
        action_fingerprint_value=str(pending["action_fingerprint"]),
        approver_provenance=provenance_from_source_channel(channel),
    )
    return result, pending
