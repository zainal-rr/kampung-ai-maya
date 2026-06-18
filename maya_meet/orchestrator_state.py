from __future__ import annotations

import asyncio
import time
from typing import Callable
from urllib.parse import urlparse, urlunparse

from maya_meet.config import RecallConfig
from maya_meet.join_models import MeetJoinOutcome
from maya_meet.recall_client import RecallBotState, RecallJoinResult
from maya_meet.store import update_meet_session


async def record_recall_state(db_path: str, session_id: str, state: RecallBotState) -> None:
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


async def poll_until_settled(
    config: RecallConfig,
    db_path: str,
    session_id: str,
    bot_id: str,
    *,
    retrieve_bot: Callable[..., RecallBotState],
    start_output: Callable[..., RecallJoinResult],
    poll_seconds: float,
    poll_interval: float,
    canonical: str = "",
) -> MeetJoinOutcome:
    deadline = time.monotonic() + max(0.0, poll_seconds)
    last_state = RecallBotState("joining", "recall_bot_joining", bot_id=bot_id)
    while True:
        state = await asyncio.to_thread(retrieve_bot, config, bot_id)
        last_state = state
        await record_recall_state(db_path, session_id, state)
        if state.is_live():
            output_failure = await ensure_output_media_started(
                config,
                db_path,
                session_id,
                bot_id,
                start_output=start_output,
                canonical=canonical,
            )
            if output_failure is not None:
                return output_failure
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


async def poll_until_left(
    config: RecallConfig,
    db_path: str,
    session_id: str,
    bot_id: str,
    *,
    retrieve_bot: Callable[..., RecallBotState],
    poll_seconds: float,
    poll_interval: float,
) -> RecallBotState:
    deadline = time.monotonic() + max(0.0, poll_seconds)
    last_state = RecallBotState("joining", "recall_leave_pending", bot_id=bot_id)
    while True:
        state = await asyncio.to_thread(retrieve_bot, config, bot_id)
        last_state = state
        await record_recall_state(db_path, session_id, state)
        if state.is_terminal():
            return state
        if time.monotonic() >= deadline:
            return last_state
        await asyncio.sleep(max(0.1, poll_interval))


async def ensure_output_media_started(
    config: RecallConfig,
    db_path: str,
    session_id: str,
    bot_id: str,
    *,
    start_output: Callable[..., RecallJoinResult],
    canonical: str = "",
) -> MeetJoinOutcome | None:
    if not config.output_media_url:
        return None
    result = await asyncio.to_thread(start_output, config, bot_id, session_id=session_id)
    await update_meet_session(db_path, session_id, output_media_status=result.reason_code)
    if result.status == "started":
        return None
    await update_meet_session(db_path, session_id, failure_reason=result.reason_code)
    return MeetJoinOutcome(
        "failed",
        "output_media_start_failed",
        session_id=session_id,
        bot_id=bot_id,
        canonical_meeting_url=canonical,
        recall_status="live",
        detail=result.detail or result.reason_code,
    )


def preflight_public_endpoints(
    config: RecallConfig,
    public_preflight: Callable[..., RecallJoinResult | None],
) -> RecallJoinResult | None:
    callback_url = config.public_callback_url.rsplit("/", 1)[0] + "/health"
    if callback_failure := public_preflight(callback_url):
        return RecallJoinResult("failed", "meet_callback_public_unhealthy", detail=callback_failure.detail)
    if output_failure := public_preflight(output_health_url(config.output_media_url)):
        return RecallJoinResult("failed", "meet_output_public_unhealthy", detail=output_failure.detail)
    return None


def output_health_url(output_media_url: str) -> str:
    parsed = urlparse(output_media_url)
    path = parsed.path.rstrip("/")
    health_path = path if path.endswith("/health") else path + "/health"
    return urlunparse((parsed.scheme, parsed.netloc, health_path, "", "", ""))
