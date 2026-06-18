from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import tempfile
import time
from pathlib import Path

from maya_core.provenance import make_provenance
from maya_meet.config import RecallConfig
from maya_meet.orchestrator import (
    canonical_meet_url,
    join_meeting as _orchestrated_join_meeting,
    leave_meeting as _orchestrated_leave_meeting,
    meet_status_text,
)
from maya_meet.recall_client import RecallBotState, RecallJoinResult
from maya_meet.store import create_meet_session, latest_meet_session_for_url, meet_session, update_meet_session


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _join(*args, **kwargs):
    kwargs.setdefault("start_output", _start_ok)
    return await _orchestrated_join_meeting(*args, **kwargs)


async def _leave(*args, **kwargs):
    return await _orchestrated_leave_meeting(*args, **kwargs)


async def main() -> None:
    config = RecallConfig(
        api_key="recall-test-key",
        base_url="https://us-west-2.recall.ai/api/v1",
        verification_secret="whsec_test",
        public_callback_url="https://maya-meet.labsoft.uk/recall/webhook",
        output_media_url="https://maya-meet.labsoft.uk/meet/output",
        output_media_token="token",
    )
    canonical = canonical_meet_url("https://meet.google.com/ASZ-WKRY-NQP?pli=1")
    _require(canonical == "https://meet.google.com/asz-wkry-nqp", canonical)
    try:
        canonical_meet_url("https://example.com/asz-wkry-nqp")
    except ValueError:
        pass
    else:
        raise AssertionError("non-Meet URL should reject")

    with tempfile.TemporaryDirectory(prefix="maya-meet-join-") as tmp:
        db_path = str(Path(tmp) / "meet.db")
        non_owner = await _join(
            canonical,
            db_path=db_path,
            config=config,
            provenance=make_provenance("other_speaker"),
            create_bot=_create_counter({}),
            retrieve_bot=_state_sequence([]),
            public_preflight=_healthy,
        )
        _require(non_owner.reason_code == "meet_join_requires_owner_text", str(non_owner))

        non_owner_leave = await _leave(
            canonical,
            db_path=db_path,
            config=config,
            provenance=make_provenance("other_speaker"),
            retrieve_bot=_state_sequence([]),
            leave_bot=_leave_counter([]),
        )
        _require(non_owner_leave.reason_code == "meet_leave_requires_owner_text", str(non_owner_leave))

        no_session_leave = await _leave(
            canonical,
            db_path=db_path,
            config=config,
            provenance=make_provenance("owner_text"),
            retrieve_bot=_state_sequence([]),
            leave_bot=_leave_counter([]),
        )
        _require(no_session_leave.reason_code == "meet_leave_no_session", str(no_session_leave))

        unhealthy_calls: list[str] = []
        unhealthy = await _join(
            canonical,
            db_path=db_path,
            config=config,
            provenance=make_provenance("owner_text"),
            create_bot=_create_counter(unhealthy_calls),
            retrieve_bot=_state_sequence([]),
            public_preflight=_unhealthy,
        )
        _require(unhealthy.status == "failed" and unhealthy.reason_code == "meet_callback_public_unhealthy", str(unhealthy))
        _require(not unhealthy_calls, "unhealthy public endpoint should not create bot")

        created_calls: list[str] = []
        joined = await _join(
            canonical,
            db_path=db_path,
            config=config,
            provenance=make_provenance("owner_text"),
            create_bot=_create_counter(created_calls, bot_id="bot_live"),
            retrieve_bot=_state_sequence([
                RecallBotState("joining", "recall_bot_joining", bot_id="bot_live", raw_status="joining_call"),
                RecallBotState("live", "recall_bot_live", bot_id="bot_live", raw_status="in_call_recording"),
            ]),
            public_preflight=_healthy,
            poll_seconds=1,
            poll_interval=0.01,
        )
        _require(joined.status == "live" and len(created_calls) == 1, str(joined))
        row = await meet_session(db_path, joined.session_id)
        _require(
            row
            and row["canonical_meeting_url"] == canonical
            and row["recall_status"] == "in_call_recording"
            and row["output_media_status"] == "output_media_started",
            str(row),
        )

        output_failure_url = "https://meet.google.com/zzz-yyyy-xxx"
        output_failed = await _join(
            output_failure_url,
            db_path=db_path,
            config=config,
            provenance=make_provenance("owner_text"),
            create_bot=_create_counter([], bot_id="bot_output_failed"),
            retrieve_bot=_state_sequence([RecallBotState("live", "recall_bot_live", bot_id="bot_output_failed", raw_status="in_call_recording")]),
            start_output=_start_failed,
            public_preflight=_healthy,
            poll_seconds=0.1,
            poll_interval=0.01,
        )
        _require(output_failed.status == "failed" and output_failed.reason_code == "output_media_start_failed", str(output_failed))

        reused = await _join(
            canonical,
            db_path=db_path,
            config=config,
            provenance=make_provenance("owner_text"),
            create_bot=_create_counter([]),
            retrieve_bot=_state_sequence([RecallBotState("live", "recall_bot_live", bot_id="bot_live", raw_status="in_call_recording")]),
            public_preflight=_healthy,
            poll_seconds=0.1,
            poll_interval=0.01,
        )
        _require(reused.reason_code == "meet_bot_reused" and reused.bot_id == "bot_live", str(reused))

        leave_calls: list[str] = []
        left = await _leave(
            canonical,
            db_path=db_path,
            config=config,
            provenance=make_provenance("owner_text"),
            retrieve_bot=_state_sequence([
                RecallBotState("live", "recall_bot_live", bot_id="bot_live", raw_status="in_call_recording"),
                RecallBotState("ended", "recall_bot_ended", bot_id="bot_live", raw_status="done"),
            ]),
            leave_bot=_leave_counter(leave_calls),
            poll_seconds=0.1,
            poll_interval=0.01,
        )
        _require(left.status == "stopped" and leave_calls == ["bot_live"], str((left, leave_calls)))
        left_row = await meet_session(db_path, joined.session_id)
        _require(
            left_row
            and left_row["status"] == "stopped"
            and left_row["recall_status"] == "done"
            and left_row["failure_reason"] == "stopped_by_telegram_leave_call",
            str(left_row),
        )

        already_ended = await _leave(
            canonical,
            db_path=db_path,
            config=config,
            provenance=make_provenance("owner_text"),
            retrieve_bot=_state_sequence([RecallBotState("ended", "recall_bot_ended", bot_id="bot_live", raw_status="done")]),
            leave_bot=_leave_counter([]),
        )
        _require(already_ended.status == "ended" and already_ended.reason_code == "meet_bot_already_ended", str(already_ended))

        stale_url = "https://meet.google.com/bbb-cccc-ddd"
        await create_meet_session(
            db_path,
            session_id="old_stale",
            meeting_url=stale_url,
            canonical_meeting_url=stale_url,
            trigger_source="test",
            provenance_source="owner_text",
        )
        await update_meet_session(db_path, "old_stale", bot_id="bot_old", status="live")
        stale_created: list[str] = []
        fresh = await _join(
            stale_url,
            db_path=db_path,
            config=config,
            provenance=make_provenance("owner_text"),
            create_bot=_create_counter(stale_created, bot_id="bot_fresh"),
            retrieve_bot=_state_sequence([
                RecallBotState("ended", "recall_bot_ended", bot_id="bot_old", raw_status="done"),
                RecallBotState("live", "recall_bot_live", bot_id="bot_fresh", raw_status="in_call_recording"),
            ]),
            public_preflight=_healthy,
            poll_seconds=0.2,
            poll_interval=0.01,
        )
        _require(fresh.status == "live" and stale_created == ["https://meet.google.com/bbb-cccc-ddd"], str(fresh))
        stale_row = await meet_session(db_path, "old_stale")
        _require(stale_row and stale_row["status"] == "stale", str(stale_row))

        transient_url = "https://meet.google.com/eee-ffff-ggg"
        await create_meet_session(
            db_path,
            session_id="retrieve_transient",
            meeting_url=transient_url,
            canonical_meeting_url=transient_url,
            trigger_source="test",
            provenance_source="owner_text",
        )
        await update_meet_session(db_path, "retrieve_transient", bot_id="bot_transient", status="live")
        transient_create_calls: list[str] = []
        transient = await _join(
            transient_url,
            db_path=db_path,
            config=config,
            provenance=make_provenance("owner_text"),
            create_bot=_create_counter(transient_create_calls, bot_id="bot_should_not_create"),
            retrieve_bot=_state_sequence([RecallBotState("failed", "recall_retrieve_failed", bot_id="bot_transient", raw_status="")]),
            public_preflight=_healthy,
            poll_seconds=0.1,
            poll_interval=0.01,
        )
        _require(transient.status == "failed" and transient.reason_code == "meet_bot_state_unknown", str(transient))
        _require(transient_create_calls == [], str(transient_create_calls))
        transient_row = await meet_session(db_path, "retrieve_transient")
        _require(transient_row and transient_row["status"] == "live", str(transient_row))

        waiting_url = "https://meet.google.com/ccc-dddd-eee"
        waiting = await _join(
            waiting_url,
            db_path=db_path,
            config=config,
            provenance=make_provenance("owner_text"),
            create_bot=_create_counter([], bot_id="bot_waiting"),
            retrieve_bot=_state_sequence([RecallBotState("waiting", "recall_bot_waiting", bot_id="bot_waiting", raw_status="in_waiting_room")]),
            public_preflight=_healthy,
            poll_seconds=0,
            poll_interval=0.01,
        )
        _require(waiting.status == "waiting" and waiting.reason_code == "waiting_room_timeout", str(waiting))

        terminal_waiting_url = "https://meet.google.com/fff-gggg-hhh"
        await create_meet_session(
            db_path,
            session_id="waiting_terminal",
            meeting_url=terminal_waiting_url,
            canonical_meeting_url=terminal_waiting_url,
            trigger_source="test",
            provenance_source="owner_text",
        )
        await update_meet_session(db_path, "waiting_terminal", bot_id="bot_waiting_terminal", status="in_waiting_room")
        terminal_waiting = await _join(
            terminal_waiting_url,
            db_path=db_path,
            config=config,
            provenance=make_provenance("owner_text"),
            create_bot=_create_counter([], bot_id="bot_should_not_create"),
            retrieve_bot=_state_sequence([
                RecallBotState("waiting", "recall_bot_waiting", bot_id="bot_waiting_terminal", raw_status="in_waiting_room"),
                RecallBotState("ended", "recall_bot_ended", bot_id="bot_waiting_terminal", raw_status="done"),
            ]),
            public_preflight=_healthy,
            poll_seconds=0.2,
            poll_interval=0.01,
        )
        _require(terminal_waiting.status == "failed" and terminal_waiting.reason_code == "recall_bot_ended", str(terminal_waiting))
        terminal_waiting_row = await meet_session(db_path, "waiting_terminal")
        _require(terminal_waiting_row and terminal_waiting_row["status"] == "ended", str(terminal_waiting_row))

        race_url = "https://meet.google.com/ddd-eeee-fff"
        race_create_calls: list[str] = []
        race_retrieve = _state_sequence([
            RecallBotState("live", "recall_bot_live", bot_id="bot_race", raw_status="in_call_recording"),
            RecallBotState("live", "recall_bot_live", bot_id="bot_race", raw_status="in_call_recording"),
        ])
        first, second = await asyncio.gather(
            _join(
                race_url,
                db_path=db_path,
                config=config,
                provenance=make_provenance("owner_text"),
                create_bot=_slow_create_counter(race_create_calls, bot_id="bot_race"),
                retrieve_bot=race_retrieve,
                public_preflight=_healthy,
                poll_seconds=0.2,
                poll_interval=0.01,
            ),
            _join(
                race_url,
                db_path=db_path,
                config=config,
                provenance=make_provenance("owner_text"),
                create_bot=_slow_create_counter(race_create_calls, bot_id="bot_race"),
                retrieve_bot=race_retrieve,
                public_preflight=_healthy,
                poll_seconds=0.2,
                poll_interval=0.01,
            ),
        )
        _require(first.status == "live" and second.status == "live", str((first, second)))
        _require(race_create_calls == ["https://meet.google.com/ddd-eeee-fff"], str(race_create_calls))

        status = await meet_status_text(
            db_path,
            meeting_url=race_url,
            config=config,
            retrieve_bot=_state_sequence([RecallBotState("live", "recall_bot_live", bot_id="bot_race", raw_status="in_call_recording")]),
        )
        _require("Recall says live" in status, status)
        status_done = await meet_status_text(
            db_path,
            meeting_url=race_url,
            config=config,
            retrieve_bot=_state_sequence([RecallBotState("ended", "recall_bot_ended", bot_id="bot_race", raw_status="done")]),
        )
        _require("Recall says ended" in status_done, status_done)
        race_row = await latest_meet_session_for_url(db_path, race_url)
        _require(race_row and race_row["status"] == "ended", str(race_row))
        latest = await latest_meet_session_for_url(db_path, canonical)
        _require(latest and latest["bot_id"] == "bot_live", str(latest))

    print("meet_join_orchestrator_smoke: ok")


def _healthy(_url: str, **_kwargs) -> None:
    return None


def _unhealthy(_url: str, **_kwargs) -> RecallJoinResult:
    return RecallJoinResult("failed", "public_url_unreachable", detail="test-down")


def _create_counter(calls, *, bot_id: str = "bot_created"):
    def create(_config, meeting_url, **_kwargs):
        calls.append(meeting_url)
        return RecallJoinResult("created", "recall_bot_created", bot_id=bot_id)
    return create


def _start_ok(_config, bot_id, **_kwargs):
    return RecallJoinResult("started", "output_media_started", bot_id=str(bot_id))


def _start_failed(_config, bot_id, **_kwargs):
    return RecallJoinResult("failed", "output_media_start_failed", bot_id=str(bot_id), detail="test output failure")


def _leave_counter(calls, *, status: str = "left", reason_code: str = "recall_leave_call_requested"):
    def leave(_config, bot_id, **_kwargs):
        calls.append(str(bot_id))
        return RecallJoinResult(status, reason_code, bot_id=str(bot_id))
    return leave


def _slow_create_counter(calls, *, bot_id: str):
    def create(_config, meeting_url, **_kwargs):
        time.sleep(0.05)
        calls.append(meeting_url)
        return RecallJoinResult("created", "recall_bot_created", bot_id=bot_id)
    return create


def _state_sequence(states: list[RecallBotState]):
    queue = list(states)

    def retrieve(_config, bot_id, **_kwargs):
        if queue:
            return queue.pop(0)
        return RecallBotState("live", "recall_bot_live", bot_id=str(bot_id), raw_status="in_call_recording")

    return retrieve


if __name__ == "__main__":
    asyncio.run(main())
