from __future__ import annotations

import asyncio
import time
import uuid
from typing import Callable

from maya_core.provenance import ProvenanceContext, make_provenance
from maya_meet.config import RecallConfig, recall_config_from_env
from maya_meet.join_models import MeetJoinOutcome, canonical_meet_url
from maya_meet.orchestrator_locks import meet_lock
from maya_meet.orchestrator_state import ensure_output_media_started, poll_until_settled, preflight_public_endpoints, record_recall_state
from maya_meet.recall_client import RecallBotState, RecallJoinResult, create_recall_bot, preflight_public_url, retrieve_recall_bot, start_output_media
from maya_meet.store import create_meet_session, latest_meet_session, latest_meet_session_for_url, update_meet_session


async def join_meeting(
    meeting_url: str,
    *,
    db_path: str,
    provenance: ProvenanceContext | None = None,
    trigger: str = "telegram",
    session_id: str | None = None,
    config: RecallConfig | None = None,
    create_bot: Callable[..., RecallJoinResult] = create_recall_bot,
    retrieve_bot: Callable[..., RecallBotState] = retrieve_recall_bot,
    start_output: Callable[..., RecallJoinResult] = start_output_media,
    public_preflight: Callable[..., RecallJoinResult | None] = preflight_public_url,
    poll_seconds: float = 30.0,
    poll_interval: float = 2.0,
) -> MeetJoinOutcome:
    provenance = provenance or make_provenance("unknown")
    if provenance.source_kind != "owner_text":
        return MeetJoinOutcome("failed", "meet_join_requires_owner_text", detail=provenance.source_kind)
    try:
        canonical = canonical_meet_url(meeting_url)
    except ValueError as exc:
        return MeetJoinOutcome("failed", "invalid_meet_url", detail=str(exc))
    async with meet_lock(canonical):
        return await _join_meeting_locked(
            canonical,
            db_path=db_path,
            provenance=provenance,
            trigger=trigger,
            session_id=session_id,
            config=config,
            create_bot=create_bot,
            retrieve_bot=retrieve_bot,
            start_output=start_output,
            public_preflight=public_preflight,
            poll_seconds=poll_seconds,
            poll_interval=poll_interval,
        )


async def meet_status_text(
    db_path: str,
    *,
    meeting_url: str = "",
    config: RecallConfig | None = None,
    retrieve_bot: Callable[..., RecallBotState] = retrieve_recall_bot,
) -> str:
    canonical = ""
    if meeting_url.strip():
        try:
            canonical = canonical_meet_url(meeting_url)
        except ValueError as exc:
            return f"Meet status: invalid Meet URL ({exc})."
        row = await latest_meet_session_for_url(db_path, canonical)
    else:
        row = await latest_meet_session(db_path)
    if row is None:
        return "Meet status: no Meet session recorded yet." if not canonical else "Meet status: no session for that Meet link."
    bot_id = str(row.get("bot_id") or "")
    if not bot_id:
        return f"Meet status: {row.get('status') or 'unknown'} for {row.get('session_id') or ''}."
    recall_config = config or recall_config_from_env()
    state = await asyncio.to_thread(retrieve_bot, recall_config, bot_id)
    await record_recall_state(db_path, str(row["session_id"]), state)
    return f"Meet status: Recall says {state.status} ({state.raw_status or state.reason_code}) for session {row['session_id']}."


async def _join_meeting_locked(
    canonical: str,
    *,
    db_path: str,
    provenance: ProvenanceContext,
    trigger: str,
    session_id: str | None,
    config: RecallConfig | None,
    create_bot: Callable[..., RecallJoinResult],
    retrieve_bot: Callable[..., RecallBotState],
    start_output: Callable[..., RecallJoinResult],
    public_preflight: Callable[..., RecallJoinResult | None],
    poll_seconds: float,
    poll_interval: float,
) -> MeetJoinOutcome:
    recall_config = config or recall_config_from_env()
    existing = await latest_meet_session_for_url(db_path, canonical)
    if existing and existing.get("bot_id"):
        outcome = await _reuse_or_mark_stale(
            recall_config,
            db_path,
            canonical,
            existing,
            retrieve_bot=retrieve_bot,
            start_output=start_output,
            poll_seconds=poll_seconds,
            poll_interval=poll_interval,
        )
        if outcome is not None:
            return outcome
    endpoint_failure = await asyncio.to_thread(preflight_public_endpoints, recall_config, public_preflight)
    if endpoint_failure is not None:
        return MeetJoinOutcome("failed", endpoint_failure.reason_code, meeting_url=canonical, canonical_meeting_url=canonical, detail=endpoint_failure.detail)
    clean_session_id = session_id or "meet_" + uuid.uuid4().hex
    await create_meet_session(
        db_path,
        session_id=clean_session_id,
        meeting_url=canonical,
        canonical_meeting_url=canonical,
        trigger_source=trigger,
        provenance_source=provenance.source_kind,
    )
    result = await asyncio.to_thread(create_bot, recall_config, canonical, session_id=clean_session_id, preflight_output=True)
    if result.status != "created":
        await update_meet_session(db_path, clean_session_id, status="join_failed", failure_reason=result.reason_code)
        return MeetJoinOutcome("failed", result.reason_code, session_id=clean_session_id, bot_id=result.bot_id, meeting_url=canonical, canonical_meeting_url=canonical, detail=result.detail)
    await update_meet_session(db_path, clean_session_id, bot_id=result.bot_id, status="bot_created")
    return await poll_until_settled(
        recall_config,
        db_path,
        clean_session_id,
        result.bot_id,
        retrieve_bot=retrieve_bot,
        start_output=start_output,
        poll_seconds=poll_seconds,
        poll_interval=poll_interval,
        canonical=canonical,
    )


async def _reuse_or_mark_stale(
    recall_config: RecallConfig,
    db_path: str,
    canonical: str,
    existing: dict[str, object],
    *,
    retrieve_bot: Callable[..., RecallBotState],
    start_output: Callable[..., RecallJoinResult],
    poll_seconds: float,
    poll_interval: float,
) -> MeetJoinOutcome | None:
    session_id = str(existing["session_id"])
    existing_bot = str(existing["bot_id"])
    state = await asyncio.to_thread(retrieve_bot, recall_config, existing_bot)
    await record_recall_state(db_path, session_id, state)
    bot_id = state.bot_id or existing_bot
    if state.is_live():
        output_failure = await ensure_output_media_started(recall_config, db_path, session_id, bot_id, start_output=start_output, canonical=canonical)
        if output_failure is not None:
            return output_failure
        return MeetJoinOutcome("live", "meet_bot_reused", session_id=session_id, bot_id=bot_id, meeting_url=canonical, canonical_meeting_url=canonical, recall_status=state.status)
    if state.is_waiting() or state.status == "joining":
        return await poll_until_settled(
            recall_config,
            db_path,
            session_id,
            bot_id,
            retrieve_bot=retrieve_bot,
            start_output=start_output,
            poll_seconds=poll_seconds,
            poll_interval=poll_interval,
        )
    if not state.is_terminal():
        return MeetJoinOutcome("failed", "meet_bot_state_unknown", session_id=session_id, bot_id=bot_id, meeting_url=canonical, canonical_meeting_url=canonical, recall_status=state.status, detail=state.raw_status or state.detail)
    await update_meet_session(
        db_path,
        session_id,
        status="stale",
        failure_reason=state.reason_code,
        recall_status=state.raw_status or state.status,
        recall_sub_code=state.sub_code,
        recall_checked_at=time.time(),
    )
    return None
