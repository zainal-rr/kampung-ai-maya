from __future__ import annotations

import asyncio
import time
import uuid
from typing import Callable
from urllib.parse import urlparse, urlunparse

from maya_core.provenance import ProvenanceContext, make_provenance
from maya_meet.config import RecallConfig, recall_config_from_env
from maya_meet.join_models import MeetJoinOutcome, canonical_meet_url
from maya_meet.recall_client import (
    RecallBotState,
    RecallJoinResult,
    create_recall_bot,
    preflight_public_url,
    retrieve_recall_bot,
)
from maya_meet.store import create_meet_session, latest_meet_session, latest_meet_session_for_url, update_meet_session


_JOIN_LOCKS: dict[str, asyncio.Lock] = {}


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
    lock = _JOIN_LOCKS.setdefault(canonical, asyncio.Lock())
    async with lock:
        return await _join_meeting_locked(
            canonical,
            db_path=db_path,
            provenance=provenance,
            trigger=trigger,
            session_id=session_id,
            config=config,
            create_bot=create_bot,
            retrieve_bot=retrieve_bot,
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
    row = None
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
    await _record_recall_state(db_path, str(row["session_id"]), state)
    return (
        f"Meet status: Recall says {state.status}"
        f" ({state.raw_status or state.reason_code}) for session {row['session_id']}."
    )


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
    public_preflight: Callable[..., RecallJoinResult | None],
    poll_seconds: float,
    poll_interval: float,
) -> MeetJoinOutcome:
    recall_config = config or recall_config_from_env()
    existing = await latest_meet_session_for_url(db_path, canonical)
    if existing and existing.get("bot_id"):
        state = await asyncio.to_thread(retrieve_bot, recall_config, str(existing["bot_id"]))
        await _record_recall_state(db_path, str(existing["session_id"]), state)
        if state.is_live():
            return MeetJoinOutcome(
                "live",
                "meet_bot_reused",
                session_id=str(existing["session_id"]),
                bot_id=state.bot_id or str(existing["bot_id"]),
                meeting_url=canonical,
                canonical_meeting_url=canonical,
                recall_status=state.status,
            )
        if state.is_waiting() or state.status == "joining":
            outcome = await _poll_until_settled(
                recall_config,
                db_path,
                str(existing["session_id"]),
                state.bot_id or str(existing["bot_id"]),
                retrieve_bot=retrieve_bot,
                poll_seconds=poll_seconds,
                poll_interval=poll_interval,
            )
            return outcome
        if not state.is_terminal():
            return MeetJoinOutcome(
                "failed",
                "meet_bot_state_unknown",
                session_id=str(existing["session_id"]),
                bot_id=state.bot_id or str(existing["bot_id"]),
                meeting_url=canonical,
                canonical_meeting_url=canonical,
                recall_status=state.status,
                detail=state.raw_status or state.detail,
            )
        await update_meet_session(
            db_path,
            str(existing["session_id"]),
            status="stale",
            failure_reason=state.reason_code,
            recall_status=state.raw_status or state.status,
            recall_sub_code=state.sub_code,
            recall_checked_at=time.time(),
        )
    endpoint_failure = await asyncio.to_thread(_preflight_public_endpoints, recall_config, public_preflight)
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
        return MeetJoinOutcome(
            "failed",
            result.reason_code,
            session_id=clean_session_id,
            bot_id=result.bot_id,
            meeting_url=canonical,
            canonical_meeting_url=canonical,
            detail=result.detail,
        )
    await update_meet_session(db_path, clean_session_id, bot_id=result.bot_id, status="bot_created")
    return await _poll_until_settled(
        recall_config,
        db_path,
        clean_session_id,
        result.bot_id,
        retrieve_bot=retrieve_bot,
        poll_seconds=poll_seconds,
        poll_interval=poll_interval,
        canonical=canonical,
    )


async def _poll_until_settled(
    config: RecallConfig,
    db_path: str,
    session_id: str,
    bot_id: str,
    *,
    retrieve_bot: Callable[..., RecallBotState],
    poll_seconds: float,
    poll_interval: float,
    canonical: str = "",
) -> MeetJoinOutcome:
    deadline = time.monotonic() + max(0.0, poll_seconds)
    last_state = RecallBotState("joining", "recall_bot_joining", bot_id=bot_id)
    while True:
        state = await asyncio.to_thread(retrieve_bot, config, bot_id)
        last_state = state
        await _record_recall_state(db_path, session_id, state)
        if state.is_live():
            await update_meet_session(db_path, session_id, status="live")
            return MeetJoinOutcome("live", "recall_bot_live", session_id=session_id, bot_id=bot_id, canonical_meeting_url=canonical, recall_status=state.status)
        if state.is_waiting():
            await update_meet_session(db_path, session_id, status="in_waiting_room", failure_reason="waiting_for_admission")
            if time.monotonic() >= deadline:
                return MeetJoinOutcome(
                    "waiting",
                    "waiting_room_timeout",
                    session_id=session_id,
                    bot_id=bot_id,
                    canonical_meeting_url=canonical,
                    recall_status=state.status,
                    detail="Maya is still waiting to be admitted.",
                )
        elif state.is_terminal():
            await update_meet_session(db_path, session_id, status=state.status, failure_reason=state.reason_code)
            return MeetJoinOutcome("failed", state.reason_code, session_id=session_id, bot_id=bot_id, canonical_meeting_url=canonical, recall_status=state.status, detail=state.raw_status)
        if time.monotonic() >= deadline:
            return MeetJoinOutcome("joining", "join_poll_timeout", session_id=session_id, bot_id=bot_id, canonical_meeting_url=canonical, recall_status=last_state.status)
        await asyncio.sleep(max(0.1, poll_interval))


async def _record_recall_state(db_path: str, session_id: str, state: RecallBotState) -> None:
    fields: dict[str, object] = {
        "recall_status": state.raw_status or state.status,
        "recall_sub_code": state.sub_code,
        "recall_checked_at": time.time(),
        "failure_reason": "" if state.is_live() else state.reason_code,
    }
    if state.is_live():
        fields["status"] = "live"
    elif state.is_waiting():
        fields["status"] = "in_waiting_room"
    elif state.is_terminal():
        fields["status"] = state.status
    await update_meet_session(db_path, session_id, **fields)


def _preflight_public_endpoints(
    config: RecallConfig,
    public_preflight: Callable[..., RecallJoinResult | None],
) -> RecallJoinResult | None:
    callback_url = config.public_callback_url.rsplit("/", 1)[0] + "/health"
    callback_failure = public_preflight(callback_url)
    if callback_failure is not None:
        return RecallJoinResult("failed", "meet_callback_public_unhealthy", detail=callback_failure.detail)
    output_failure = public_preflight(_output_health_url(config.output_media_url))
    if output_failure is not None:
        return RecallJoinResult("failed", "meet_output_public_unhealthy", detail=output_failure.detail)
    return None


def _output_health_url(output_media_url: str) -> str:
    parsed = urlparse(output_media_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/health"):
        health_path = path
    else:
        health_path = path + "/health"
    return urlunparse((parsed.scheme, parsed.netloc, health_path, "", "", ""))


def _waiting_outcome(existing: dict[str, object], state: RecallBotState, canonical: str) -> MeetJoinOutcome:
    return MeetJoinOutcome(
        "waiting",
        "waiting_room_timeout",
        session_id=str(existing["session_id"]),
        bot_id=state.bot_id or str(existing.get("bot_id") or ""),
        meeting_url=canonical,
        canonical_meeting_url=canonical,
        recall_status=state.status,
        detail="Maya is still waiting to be admitted.",
    )
