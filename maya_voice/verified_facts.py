from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


VOLATILE_FACT_TTL_SECONDS = 3.0


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def file_fact(path: str | Path, *, opened: bool | None = None, app: str = "", volatile: bool = False) -> dict[str, Any]:
    target = Path(path)
    fact: dict[str, Any] = {
        "artifact_path": str(target),
        "file_exists": target.exists(),
        "file_created": target.exists(),
        "captured_at": now_iso(),
        "volatile": volatile,
    }
    if opened is not None:
        fact["file_opened"] = bool(opened)
    if app:
        fact["frontmost_app"] = app
    return fact


def browser_fact(
    *,
    bridge_connected: bool,
    opened_in_maya_group: bool = False,
    url: str = "",
    title: str = "",
    window_id: int | str = "",
    group_id: int | str = "",
    tab_id: int | str = "",
    reason_code: str = "",
    server_pid: int | str = "",
) -> dict[str, Any]:
    fact = {
        "browser_bridge_connected": bool(bridge_connected),
        "opened_in_maya_group": bool(opened_in_maya_group),
        "window_id": window_id,
        "group_id": group_id,
        "tab_id": tab_id,
        "url": url,
        "title": title,
        "captured_at": now_iso(),
        "volatile": True,
    }
    if reason_code:
        fact["reason_code"] = reason_code
    if server_pid:
        fact["server_pid"] = server_pid
    return fact


def work_fact(*, work_active: bool, phase: str = "", work_id: str = "") -> dict[str, Any]:
    return {
        "work_active": bool(work_active),
        "phase": phase,
        "work_id": work_id,
        "captured_at": now_iso(),
        "volatile": True,
    }


def facts_block(facts: list[dict[str, Any]] | dict[str, Any] | None) -> str:
    if not facts:
        return ""
    return "Verified facts:\n" + json.dumps(facts, sort_keys=True, ensure_ascii=True)
