from __future__ import annotations

import hashlib
import json

import aiosqlite

from maya_harness.harness_store import init_harness_db
from maya_harness.harness_tools import HarnessToolResult


UNSAFE_REPLAY_ACTIONS = ("browser:click", "browser:fill", "app:", "send", "payment", "booking", "external_image")


async def init_action_ledger(db_path: str) -> None:
    await init_harness_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS harness_action_ledger (
                idempotency_key TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                node TEXT NOT NULL,
                workflow_type TEXT NOT NULL,
                action TEXT NOT NULL,
                canonical_args_json TEXT DEFAULT '{}',
                status TEXT DEFAULT 'planned',
                result_json TEXT DEFAULT '{}',
                artifact_paths_json TEXT DEFAULT '[]',
                precondition_json TEXT DEFAULT '{}',
                postcondition_json TEXT DEFAULT '{}',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


def action_key(*, thread_id: str, run_id: str, node: str, action: str, args: dict, user_turn_id: str) -> str:
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"))
    raw = "|".join((thread_id, run_id, node, action, canonical, user_turn_id))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def begin_action(db_path: str, *, key: str, run_id: str, thread_id: str, node: str, workflow_type: str, action: str, args: dict) -> dict:
    await init_action_ledger(db_path)
    canonical = json.dumps(args, sort_keys=True)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM harness_action_ledger WHERE idempotency_key = ?", (key,))
        row = await cursor.fetchone()
        if row:
            data = dict(row)
            data["existing"] = True
            return data
        await db.execute(
            """
            INSERT INTO harness_action_ledger (
                idempotency_key, run_id, thread_id, node, workflow_type, action,
                canonical_args_json, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'in_progress')
            """,
            (key, run_id, thread_id, node, workflow_type, action, canonical),
        )
        await db.commit()
    return {"idempotency_key": key, "status": "in_progress", "existing": False}


async def finish_action(db_path: str, key: str, result: HarnessToolResult, status: str = "succeeded") -> None:
    await init_action_ledger(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE harness_action_ledger
            SET status = ?, result_json = ?, artifact_paths_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE idempotency_key = ?
            """,
            (status, _result_json(result), json.dumps(result.artifacts), key),
        )
        await db.commit()


async def mark_unknown(db_path: str, key: str, reason: str) -> None:
    await init_action_ledger(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            UPDATE harness_action_ledger
            SET status = 'unknown', postcondition_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE idempotency_key = ?
            """,
            (json.dumps({"reason": reason}), key),
        )
        await db.commit()


def cached_result(row: dict) -> HarnessToolResult:
    data = json.loads(row.get("result_json") or "{}")
    return HarnessToolResult(
        status=str(data.get("status") or "completed"),
        message=str(data.get("message") or ""),
        artifacts=list(data.get("artifacts") or []),
        requires_approval=bool(data.get("requires_approval") or False),
        next_step=str(data.get("next_step") or ""),
        keep_open=bool(data.get("keep_open") or False),
        model_lane=str(data.get("model_lane") or ""),
        cost_recorded=bool(data.get("cost_recorded") or False),
    )


def should_pause_unknown(action: str, text: str) -> bool:
    lowered = f"{action} {text}".lower()
    return any(marker in lowered for marker in UNSAFE_REPLAY_ACTIONS)


def _result_json(result: HarnessToolResult) -> str:
    return json.dumps(
        {
            "status": result.status,
            "message": result.message,
            "artifacts": result.artifacts,
            "requires_approval": result.requires_approval,
            "next_step": result.next_step,
            "keep_open": result.keep_open,
            "model_lane": result.model_lane,
            "cost_recorded": result.cost_recorded,
        }
    )
