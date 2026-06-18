from __future__ import annotations

import asyncio
import time
from typing import Callable

from maya_core.provenance import ProvenanceContext, make_provenance
from maya_meet.config import RecallConfig, recall_config_from_env
from maya_meet.join_models import MeetJoinOutcome, canonical_meet_url
from maya_meet.orchestrator_locks import meet_lock
from maya_meet.orchestrator_state import poll_until_left, record_recall_state
from maya_meet.recall_client import RecallBotState, RecallJoinResult, leave_recall_bot, retrieve_recall_bot
from maya_meet.store import latest_meet_session, latest_meet_session_for_url, update_meet_session


async def leave_meeting(
    meeting_url: str = "",
    *,
    db_path: str,
    provenance: ProvenanceContext | None = None,
    trigger: str = "telegram",
    config: RecallConfig | None = None,
    retrieve_bot: Callable[..., RecallBotState] = retrieve_recall_bot,
    leave_bot: Callable[..., RecallJoinResult] = leave_recall_bot,
    poll_seconds: float = 10.0,
    poll_interval: float = 0.5,
) -> MeetJoinOutcome:
    provenance = provenance or make_provenance("unknown")
    if provenance.source_kind != "owner_text":
        return MeetJoinOutcome("failed", "meet_leave_requires_owner_text", detail=provenance.source_kind)
    canonical = ""
    if meeting_url.strip():
        try:
            canonical = canonical_meet_url(meeting_url)
        except ValueError as exc:
            return MeetJoinOutcome("failed", "invalid_meet_url", detail=str(exc))
    async with meet_lock(canonical or "__latest_meet_leave__"):
        return await _leave_meeting_locked(
            canonical,
            db_path=db_path,
            trigger=trigger,
            config=config,
            retrieve_bot=retrieve_bot,
            leave_bot=leave_bot,
            poll_seconds=poll_seconds,
            poll_interval=poll_interval,
        )


async def _leave_meeting_locked(
    canonical: str,
    *,
    db_path: str,
    trigger: str,
    config: RecallConfig | None,
    retrieve_bot: Callable[..., RecallBotState],
    leave_bot: Callable[..., RecallJoinResult],
    poll_seconds: float,
    poll_interval: float,
) -> MeetJoinOutcome:
    del trigger
    row = await latest_meet_session_for_url(db_path, canonical) if canonical else await latest_meet_session(db_path)
    if row is None:
        return MeetJoinOutcome("failed", "meet_leave_no_session", canonical_meeting_url=canonical)
    session_id = str(row.get("session_id") or "")
    bot_id = str(row.get("bot_id") or "")
    row_canonical = str(row.get("canonical_meeting_url") or canonical or row.get("meeting_url") or "")
    if not bot_id:
        await update_meet_session(db_path, session_id, status="stale", failure_reason="meet_leave_missing_bot_id", recall_checked_at=time.time())
        return MeetJoinOutcome("failed", "meet_leave_missing_bot_id", session_id=session_id, canonical_meeting_url=row_canonical)
    recall_config = config or recall_config_from_env()
    state = await asyncio.to_thread(retrieve_bot, recall_config, bot_id)
    await record_recall_state(db_path, session_id, state)
    if state.is_terminal():
        return MeetJoinOutcome("ended", "meet_bot_already_ended", session_id=session_id, bot_id=bot_id, canonical_meeting_url=row_canonical, recall_status=state.status, detail=state.raw_status or state.detail)
    if state.status == "failed":
        return MeetJoinOutcome("failed", "meet_leave_recall_state_unknown", session_id=session_id, bot_id=bot_id, canonical_meeting_url=row_canonical, recall_status=state.status, detail=state.detail or state.raw_status)
    result = await asyncio.to_thread(leave_bot, recall_config, bot_id)
    if result.status != "left":
        await update_meet_session(db_path, session_id, failure_reason=result.reason_code, recall_checked_at=time.time())
        return MeetJoinOutcome("failed", result.reason_code, session_id=session_id, bot_id=bot_id, canonical_meeting_url=row_canonical, recall_status=state.status, detail=result.detail)
    return await _confirm_left(recall_config, db_path, session_id, bot_id, row_canonical, retrieve_bot=retrieve_bot, poll_seconds=poll_seconds, poll_interval=poll_interval)


async def _confirm_left(
    recall_config: RecallConfig,
    db_path: str,
    session_id: str,
    bot_id: str,
    canonical: str,
    *,
    retrieve_bot: Callable[..., RecallBotState],
    poll_seconds: float,
    poll_interval: float,
) -> MeetJoinOutcome:
    final_state = await poll_until_left(recall_config, db_path, session_id, bot_id, retrieve_bot=retrieve_bot, poll_seconds=poll_seconds, poll_interval=poll_interval)
    if final_state.is_terminal():
        await update_meet_session(
            db_path,
            session_id,
            status="stopped",
            failure_reason="stopped_by_telegram_leave_call",
            recall_status=final_state.raw_status or final_state.status,
            recall_sub_code=final_state.sub_code,
            recall_checked_at=time.time(),
        )
        return MeetJoinOutcome("stopped", "recall_leave_call_requested", session_id=session_id, bot_id=bot_id, canonical_meeting_url=canonical, recall_status=final_state.status, detail=final_state.raw_status or final_state.detail)
    await update_meet_session(
        db_path,
        session_id,
        status="stopping",
        failure_reason="leave_poll_timeout",
        recall_status=final_state.raw_status or final_state.status,
        recall_sub_code=final_state.sub_code,
        recall_checked_at=time.time(),
    )
    return MeetJoinOutcome("stopping", "leave_poll_timeout", session_id=session_id, bot_id=bot_id, canonical_meeting_url=canonical, recall_status=final_state.status, detail=final_state.raw_status or final_state.detail)
