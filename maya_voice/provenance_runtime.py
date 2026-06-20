from __future__ import annotations

from uuid import uuid4

import aiosqlite

from maya_core.provenance import (
    ProvenanceContext,
    merge_provenance,
    provenance_action_decision,
    provenance_from_json,
    provenance_from_tool_args,
    provenance_to_json,
)
from maya_voice.confirmation import create_pending_confirmation
from maya_voice.tool_results import tool_result_for_maya

TABLE = "voice_session_provenance_carry"


async def init_voice_provenance_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE} (
                voice_session_id TEXT PRIMARY KEY,
                provenance_json TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def remember_session_provenance(db_path: str, voice_session_id: str, provenance: ProvenanceContext) -> None:
    if not voice_session_id or not (provenance.untrusted_influence or provenance.injection_detected):
        return
    await init_voice_provenance_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            f"""
            INSERT INTO {TABLE} (voice_session_id, provenance_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(voice_session_id) DO UPDATE SET
                provenance_json = excluded.provenance_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (voice_session_id, provenance_to_json(provenance)),
        )
        await db.commit()


async def remember_result_provenance(
    db_path: str,
    voice_session_id: str,
    result_text: str,
    *,
    source_kind: str = "unknown",
) -> None:
    text = str(result_text or "")
    if not _result_text_has_untrusted_influence(text):
        return
    await remember_session_provenance(
        db_path,
        voice_session_id,
        ProvenanceContext(
            source_kind=source_kind,
            untrusted_influence=True,
            injection_detected="injection_detected: true" in text,
        ),
    )


def _result_text_has_untrusted_influence(text: str) -> bool:
    lowered = text.lower()
    return (
        "untrusted_influence: true" in lowered
        or "safety boundary: untrusted" in lowered
        or ("reference-only" in lowered and "untrusted" in lowered)
    )


async def effective_voice_provenance(
    db_path: str,
    args: dict,
    *,
    voice_session_id: str = "",
    default_kind: str = "owner_voice",
) -> ProvenanceContext:
    explicit = provenance_from_tool_args(args, default_kind=default_kind)
    if not voice_session_id:
        return explicit
    await init_voice_provenance_db(db_path)
    async with aiosqlite.connect(db_path) as db:
        row = await (
            await db.execute(f"SELECT provenance_json FROM {TABLE} WHERE voice_session_id = ?", (voice_session_id,))
        ).fetchone()
    if not row:
        return explicit
    carried = provenance_from_json(str(row[0] or "{}"))
    return merge_provenance(explicit, carried)


async def gate_voice_action(
    db_path: str,
    *,
    request: str,
    tool_name: str,
    payload: dict,
    provenance: ProvenanceContext,
    side_effect_level: str,
) -> str | None:
    decision, reason = provenance_action_decision(
        tool_name=tool_name,
        provenance=provenance,
        side_effect_level=side_effect_level,
    )
    if decision == "allow":
        return None
    if decision == "deny":
        return tool_result_for_maya(
            request,
            f"w7_provenance_blocked: {reason}",
            status="failed",
        )
    pending = await create_pending_confirmation(
        db_path,
        action_id=f"w7-{uuid4().hex[:16]}",
        summary=f"{tool_name}: {request}",
        payload={
            "tool_name": tool_name,
            "request": request,
            "payload": payload,
            "provenance": provenance.as_dict(),
        },
    )
    return tool_result_for_maya(
        request,
        "\n".join([
            f"w7_confirmation_required: {reason}",
            f"action_id: {pending['action_id']}",
            f"action_fingerprint: {pending['action_fingerprint']}",
            f"provenance_source: {provenance.source_kind}",
        ]),
        status="needs_confirmation",
    )
