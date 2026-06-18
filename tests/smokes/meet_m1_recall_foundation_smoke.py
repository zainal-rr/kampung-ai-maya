from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import base64
import json
import tempfile
import time
import urllib.error
from pathlib import Path
from unittest.mock import patch

import numpy as np
import aiosqlite
from aiohttp.test_utils import TestClient, TestServer

from maya_core.provenance import make_provenance, provenance_from_source_channel
from maya_meet.approval import claim_approved_meeting_actions, resolve_meeting_approval_command
from maya_meet.actions import meeting_action_class
from maya_meet.audio_wake import RecallAudioWakeState
from maya_meet.config import RecallConfig
from maya_meet.engagement import addressed_to_maya, meet_address_decision, strip_maya_address
from maya_meet.output_media import MeetOutputQueue
from maya_meet.policy import meeting_turn_decision
from maya_meet.recall_client import create_bot_payload, create_recall_bot
from maya_meet.recall_events import handle_recall_event
from maya_meet.responder import MeetM1Responder
from maya_meet.recall_security import recall_test_signature, verify_recall_signature
from maya_meet.service import _maya_session_id, create_meet_app
from maya_meet.store import create_meet_session, meet_session
from maya_voice.confirmation import action_fingerprint, confirm_action, create_pending_confirmation


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    asyncio.run(_run())
    print("meet_m1_recall_foundation_smoke: ok")


async def _run() -> None:
    secret = "whsec_" + base64.b64encode(b"maya-recall-test-secret").decode("ascii")
    payload = json.dumps({"event": "transcript.data", "speaker": "Colleague", "text": "Maya, summarize this"})
    headers = _headers(secret, payload)
    verify_recall_signature(secret=secret, headers=headers, payload=payload)
    bad = dict(headers)
    bad["webhook-signature"] = "v1,bad"
    stale = _headers(secret, payload, timestamp=str(int(time.time()) - 1000))
    with tempfile.TemporaryDirectory(prefix="maya-meet-m1-") as tmp:
        db_path = str(Path(tmp) / "meet.db")
        await create_meet_session(db_path, session_id="m1", meeting_url="https://meet.google.com/abc-defg-hij")
        accepted = await handle_recall_event(db_path, session_id="m1", secret=secret, headers=headers, raw_payload=payload)
        _require(accepted["status"] == "accepted", str(accepted))
        duplicate = await handle_recall_event(db_path, session_id="m1", secret=secret, headers=headers, raw_payload=payload)
        _require(duplicate["reason_code"] == "duplicate_recall_event", str(duplicate))
        race_payload = json.dumps({"event": "transcript.data", "speaker": "Colleague", "text": "Maya, race test"})
        race_headers = _headers(secret, race_payload, message_id="msg_race")
        race_results = await asyncio.gather(
            handle_recall_event(db_path, session_id="m1", secret=secret, headers=race_headers, raw_payload=race_payload),
            handle_recall_event(db_path, session_id="m1", secret=secret, headers=race_headers, raw_payload=race_payload),
        )
        _require(
            sorted(result["status"] for result in race_results) == ["accepted", "duplicate"],
            str(race_results),
        )
        rejected = await handle_recall_event(db_path, session_id="m1", secret=secret, headers=bad, raw_payload=payload)
        _require(rejected["status"] == "rejected", str(rejected))
        stale_result = await handle_recall_event(db_path, session_id="m1", secret=secret, headers=stale, raw_payload=payload)
        _require(stale_result["reason_code"] == "signature_timestamp_stale", str(stale_result))
        status_payload = json.dumps({
            "event": "bot.in_call_recording",
            "data": {"data": {"code": "bot.in_call_recording", "sub_code": None}, "bot": {"id": "bot_1", "metadata": {"maya_session_id": "m1"}}},
        })
        status_result = await handle_recall_event(
            db_path,
            session_id="m1",
            secret=secret,
            headers=_headers(secret, status_payload, message_id="msg_status"),
            raw_payload=status_payload,
        )
        _require(status_result["event_type"] == "bot.in_call_recording", str(status_result))
        row = await meet_session(db_path, "m1")
        _require(row and row["room_authority_level"] == "level_0_locked", str(row))
        _require(row["status"] == "bot.in_call_recording" and row["bot_id"] == "bot_1", str(row))
        nested_transcript = json.dumps({
            "event": "transcript.data",
            "data": {
                "data": {
                    "participant": {"name": "Zainal Abidin"},
                    "words": [{"text": "meeting"}, {"text": "context"}],
                }
            },
        })
        nested_result = await handle_recall_event(
            db_path,
            session_id="m1",
            secret=secret,
            headers=_headers(secret, nested_transcript, message_id="msg_nested_transcript"),
            raw_payload=nested_transcript,
        )
        _require(nested_result["event_type"] == "transcript.data", str(nested_result))
        row = await meet_session(db_path, "m1")
        _require(row and row["status"] == "live", str(row))

    _require(addressed_to_maya("Maya, what did Amir decide?"), "direct address missed")
    _require(addressed_to_maya("Maya can you summarize the last point?"), "bare direct address missed")
    _require(addressed_to_maya("Hey, Maya, summarize that"), "punctuated greeting address missed")
    _require(addressed_to_maya("Hello Maya, summarize that"), "hello direct address missed")
    _require(strip_maya_address("Hey Maya, summarize that") == "summarize that", "address strip failed")
    may_i = meet_address_decision("may i summarize the last point")
    _require(may_i.addressed and may_i.reason_code in {"addressed_wake_mangle", "addressed_fuzzy"}, str(may_i))
    _require(strip_maya_address("may i summarize the last point") == "summarize the last point", "may i strip failed")
    for variant in ("maia summarize the point", "mya summarize the point", "my a summarize the point", "meya summarize the point", "mai summarize the point"):
        decision = meet_address_decision(variant)
        _require(decision.addressed, f"wake mangle missed: {variant} -> {decision}")
    _require(not addressed_to_maya("maybe we should summarize this"), "maybe should not wake")
    _require(not addressed_to_maya("my apartment needs work"), "my apartment should not wake")
    for false_positive in ("mama summarize this", "mail summarize this", "mayo summarize this", "ma summarize this"):
        _require(not addressed_to_maya(false_positive), f"non-wake M-word should stay silent: {false_positive}")
    _require(not addressed_to_maya("check Google for this"), "request-shaped no-wake speech should stay silent")
    _require(not addressed_to_maya("I was telling Maya about the project"), "casual mention should not engage")
    _require(not addressed_to_maya("Maya is already in the meeting notes"), "sentence reference should not engage")

    other = provenance_from_source_channel("meeting_speech")
    _require(other.source_kind == "other_speaker", "meeting speech must not become owner")
    ignored = meeting_turn_decision(text="please summarize", provenance=other)
    _require(ignored.status == "ignored", str(ignored))
    answer = meeting_turn_decision(text="Maya, summarize the last point", provenance=other)
    _require(answer.status == "answer_allowed", str(answer))
    disabled = meeting_turn_decision(text="Maya, open the browser", provenance=other, action_class="lookup")
    _require(disabled.reason_code == "meeting_room_actions_disabled", str(disabled))
    contained = meeting_turn_decision(text="Maya, open the browser", provenance=other, action_class="lookup", m2_enabled=True)
    _require(contained.status == "allowed", str(contained))
    ambiguous = meeting_turn_decision(text="Maya, archive this", provenance=other, action_class="unknown_action", m2_enabled=True)
    _require(ambiguous.status == "needs_confirmation", str(ambiguous))
    private = meeting_turn_decision(text="Maya, read my private notes", provenance=other, content_class="owner_private")
    _require(private.reason_code == "owner_private_disclosure_requires_telegram", str(private))
    unknown_content = meeting_turn_decision(text="Maya, answer from this unknown content", provenance=other, content_class="unknown")
    _require(unknown_content.reason_code == "owner_private_disclosure_requires_telegram", str(unknown_content))
    owner_no_voiceprint = meeting_turn_decision(
        text="Maya, open the agenda",
        provenance=make_provenance("owner_voice_meeting"),
        action_class="lookup",
        m2_enabled=True,
    )
    _require(owner_no_voiceprint.status == "allowed", str(owner_no_voiceprint))
    _require(meeting_action_class("open Gmail") == "private_lookup", "private page should require approval")
    _require(meeting_action_class("archive this") == "approval_required", "ambiguous/risky action should require approval")
    _require(meeting_action_class("click Continue") == "private_lookup", "context-dependent click should require approval")
    _require(meeting_action_class("open link") == "private_lookup", "bare link open should require approval")
    _require(meeting_action_class("open the second link") == "lookup", "visible result navigation should stay allowed")
    _require(meeting_action_class("click result 3") == "lookup", "numbered result navigation should stay allowed")

    config = RecallConfig(
        api_key="",
        base_url="https://us-west-2.recall.ai/api/v1",
        verification_secret=secret,
        public_callback_url="https://example.test/recall",
        output_media_url="https://example.test/maya-meet",
        output_media_token="test-token",
    )
    missing = create_recall_bot(config, "https://meet.google.com/abc-defg-hij")
    _require(missing.reason_code == "recall_config_missing", str(missing))
    ready_config = RecallConfig(
        api_key="recall-test-key",
        base_url="https://us-west-2.recall.ai/api/v1",
        verification_secret=secret,
        public_callback_url="https://example.test/recall",
        output_media_url="https://example.test/maya-meet",
        output_media_token="test-token",
    )
    with patch("urllib.request.urlopen", return_value=_FakeRecallResponse({"id": "bot_123"})):
        created = create_recall_bot(ready_config, "https://meet.google.com/abc-defg-hij", session_id="m1")
    _require(created.status == "created" and created.reason_code == "recall_bot_created", str(created))
    with patch(
        "urllib.request.urlopen",
        side_effect=[_FakeRecallResponse({}), _FakeRecallResponse({"id": "bot_456"})],
    ):
        preflight_created = create_recall_bot(
            ready_config,
            "https://meet.google.com/abc-defg-hij",
            session_id="m1",
            preflight_output=True,
        )
    _require(preflight_created.status == "created", str(preflight_created))
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("output tunnel down")):
        output_failed = create_recall_bot(
            ready_config,
            "https://meet.google.com/abc-defg-hij",
            session_id="m1",
            preflight_output=True,
        )
    _require(output_failed.reason_code == "output_media_unreachable", str(output_failed))
    payload = create_bot_payload(config, "https://meet.google.com/abc-defg-hij", session_id="m1")
    _require(payload["metadata"]["maya_session_id"] == "m1", str(payload))
    _require(payload["output_media"]["camera"]["kind"] == "webpage", str(payload))
    _require("token=test-token" in payload["output_media"]["camera"]["config"]["url"], str(payload))
    endpoint = payload["recording_config"]["realtime_endpoints"][0]
    _require(endpoint["events"] == ["transcript.data"], str(payload))
    _require(
        payload["recording_config"]["transcript"]["provider"]["recallai_streaming"]["mode"] == "prioritize_low_latency",
        str(payload),
    )
    _require(
        payload["recording_config"]["transcript"]["provider"]["recallai_streaming"]["language_code"] == "en",
        str(payload),
    )
    _require("session_id=m1" in payload["output_media"]["camera"]["config"]["url"], str(payload))
    audio_config = RecallConfig(
        api_key="recall-test-key",
        base_url="https://us-west-2.recall.ai/api/v1",
        verification_secret=secret,
        public_callback_url="https://callback.example.test/recall/webhook",
        output_media_url="https://example.test/maya-meet",
        output_media_token="test-token",
        audio_wake_enabled=True,
    )
    audio_payload = create_bot_payload(audio_config, "https://meet.google.com/abc-defg-hij", session_id="m1")
    _require(audio_payload["recording_config"]["audio_mixed_raw"] == {}, str(audio_payload))
    audio_endpoint = audio_payload["recording_config"]["realtime_endpoints"][1]
    _require(audio_endpoint["type"] == "websocket", str(audio_endpoint))
    _require(audio_endpoint["events"] == ["audio_mixed_raw.data"], str(audio_endpoint))
    _require(audio_endpoint["url"].startswith("wss://callback.example.test/recall/audio-wake"), str(audio_endpoint))
    _require("token=test-token" in audio_endpoint["url"], str(audio_endpoint))
    nested = {
        "data": {
            "bot": {"metadata": {"maya_session_id": "bot_session"}},
            "recording": {"metadata": {"maya_session_id": "recording_session"}},
        }
    }
    _require(_maya_session_id(nested) == "bot_session", "bot metadata session not found")
    await _output_surface_smoke(config, secret)
    await _responder_context_smoke()


async def _responder_context_smoke() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-meet-responder-") as tmp:
        output_queue = _FakeOutputQueue()
        responder = MeetM1Responder(
            db_path=str(Path(tmp) / "meet.db"),
            output_queue=output_queue,
            voice_node=_FakeVoiceNode(Path(tmp)),
        )
        first = await responder.process_verified_event({"text": "We should meet at 3 pm."})
        _require(first["reason_code"] == "not_addressed", str(first))
        second = await responder.process_verified_event({"text": "I think that will be hard."})
        _require(second["reason_code"] == "not_addressed", str(second))
        answer = await responder.process_verified_event({"text": "Maya, what was the last spoken sentence?"})
        _require(answer["status"] == "queued", str(answer))
        _require(
            output_queue.previews[-1] == "The last spoken sentence was: I think that will be hard.",
            output_queue.previews[-1],
        )
        echo = await responder.process_verified_event({"text": output_queue.previews[-1]})
        _require(echo["reason_code"] == "maya_self_output_echo", str(echo))
        summary = await responder.process_verified_event({"text": "Maya, summarize the last point."})
        _require(summary["status"] == "queued", str(summary))
        _require("The last spoken sentence was" not in output_queue.previews[-1], output_queue.previews[-1])
        _require("We should meet at 3 pm" in output_queue.previews[-1], output_queue.previews[-1])

        fuzzy = await responder.process_verified_event({"text": "may i summarize the last point."})
        _require(fuzzy["status"] == "queued", str(fuzzy))
        _require(fuzzy["address_reason_code"] in {"addressed_wake_mangle", "addressed_fuzzy"}, str(fuzzy))

        no_wake = await responder.process_verified_event({"text": "check Google for this"})
        _require(no_wake["status"] == "ignored" and no_wake["reason_code"] == "not_addressed", str(no_wake))

        m1_browser = await responder.process_verified_event({"text": "Maya, open the browser"})
        _require(m1_browser["status"] == "queued", str(m1_browser))
        _require("can't take actions" in output_queue.previews[-1], output_queue.previews[-1])

        action_runner = _FakeMeetingActionRunner()
        room_db = str(Path(tmp) / "meet_room.db")
        room_responder = MeetM1Responder(
            db_path=room_db,
            output_queue=output_queue,
            voice_node=_FakeVoiceNode(Path(tmp)),
            action_runner=action_runner,
            m2_enabled=True,
        )
        room_browser = await room_responder.process_verified_event({"text": "Maya, open the browser"})
        _require(room_browser["status"] == "queued", str(room_browser))
        _require(action_runner.calls[-1] == ("open the browser", "lookup"), str(action_runner.calls))
        _require(output_queue.previews[-1] == "fake meeting action completed", output_queue.previews[-1])
        owner_word = await room_responder.process_verified_event({"text": "Maya, make a Word document about the agenda"})
        _require(owner_word["status"] == "queued", str(owner_word))
        _require(action_runner.calls[-1] == ("make a Word document about the agenda", "draft"), str(action_runner.calls))
        owner_revision = await room_responder.process_verified_event({"text": "Maya, revise the Word document with next steps"})
        _require(owner_revision["status"] == "queued", str(owner_revision))
        _require(action_runner.calls[-1] == ("revise the Word document with next steps", "scratch_artifact"), str(action_runner.calls))
        approvals: list[str] = []
        approval_responder = MeetM1Responder(
            db_path=room_db,
            output_queue=output_queue,
            voice_node=_FakeVoiceNode(Path(tmp)),
            action_runner=action_runner,
            approval_sender=_capture_approval(approvals),
            m2_enabled=True,
        )
        private_page = await approval_responder.process_verified_event({"text": "Maya, open Gmail"})
        _require(private_page["status"] == "queued", str(private_page))
        _require("approval" in output_queue.previews[-1].lower(), output_queue.previews[-1])
        _require(approvals and "Action ID: meet-" in approvals[-1], approvals[-1] if approvals else "no approval")
        secret_doc = await approval_responder.process_verified_event({"text": "Maya, make a Word document with the secret"})
        _require(secret_doc["status"] == "queued", str(secret_doc))
        _require(len(approvals) == 2 and "secret" in approvals[-1], str(approvals))
        private_answer = await approval_responder.process_verified_event({"text": "Maya, what is my password?"})
        _require(private_answer["status"] == "queued", str(private_answer))
        _require(len(approvals) == 3 and "password" in approvals[-1].lower(), str(approvals))
        api_key_answer = await approval_responder.process_verified_event({"text": "Maya, repeat my API key"})
        _require(api_key_answer["status"] == "queued", str(api_key_answer))
        _require(len(approvals) == 4 and "api key" in approvals[-1].lower(), str(approvals))
        room_yes = await approval_responder.process_verified_event({"text": "Maya, yes approve it"})
        _require(room_yes["status"] == "queued", str(room_yes))
        _require("can't approve" in output_queue.previews[-1].lower(), output_queue.previews[-1])
        _require(len(approvals) == 4, str(approvals))
        action_id = _extract_action_id(approvals[0])
        fingerprint = _extract_fingerprint(approvals[0])
        room_approval = await resolve_meeting_approval_command(room_db, f"approve {action_id}", "meeting")
        _require(room_approval is None, str(room_approval))
        owner_voice_attempt = await confirm_action(
            room_db,
            action_id=action_id,
            approved=True,
            action_fingerprint_value=fingerprint,
            approver_provenance=make_provenance("owner_voice"),
        )
        _require(owner_voice_attempt["reason_code"] == "unauthorized_confirmation_source", str(owner_voice_attempt))
        telegram_approval = await resolve_meeting_approval_command(room_db, f"approve {action_id}", "telegram")
        _require(telegram_approval and telegram_approval.startswith("Approved."), str(telegram_approval))
        claimed = await claim_approved_meeting_actions(room_db)
        _require(len(claimed) == 1, str(claimed))
        _require(claimed[0]["payload"]["action_class"] == "private_lookup", str(claimed))
        second_claim = await claim_approved_meeting_actions(room_db)
        _require(second_claim == [], str(second_claim))
        async with aiosqlite.connect(room_db) as db:
            status = await (await db.execute("SELECT status FROM voice_pending_confirmations WHERE action_id = ?", (action_id,))).fetchone()
        _require(status and status[0] == "executing", str(status))

        generic_payload = {"surface": "generic_test", "request": "older approved row"}
        for idx in range(6):
            pending = await create_pending_confirmation(
                room_db,
                action_id=f"generic-{idx}",
                summary="generic older approval",
                payload=generic_payload | {"idx": idx},
            )
            await confirm_action(
                room_db,
                action_id=pending["action_id"],
                approved=True,
                action_fingerprint_value=pending["action_fingerprint"],
                approver_provenance=make_provenance("owner_text"),
            )
        approvals_before = len(approvals)
        later_private = await approval_responder.process_verified_event({"text": "Maya, open my private calendar"})
        _require(later_private["status"] == "queued", str(later_private))
        _require(len(approvals) == approvals_before + 1, str(approvals))
        later_action_id = _extract_action_id(approvals[-1])
        later_fingerprint = _extract_fingerprint(approvals[-1])
        later_approved = await resolve_meeting_approval_command(room_db, f"approve {later_action_id}", "telegram")
        _require(later_approved and later_approved.startswith("Approved."), str(later_approved))
        later_claimed = await claim_approved_meeting_actions(room_db, limit=5)
        _require(len(later_claimed) == 1 and later_claimed[0]["action_id"] == later_action_id, str(later_claimed))
        async with aiosqlite.connect(room_db) as db:
            stale_result = await db.execute(
                "UPDATE voice_pending_confirmations SET status = 'approved' WHERE action_id = ? AND status = 'approved'",
                (later_action_id,),
            )
        _require(stale_result.rowcount == 0, "claimed row should not still be approved")

        tamper_request = await request_meet_approval_for_test(room_db, approvals, approval_responder, "Maya, open my private inbox")
        tamper_action_id = _extract_action_id(approvals[-1])
        async with aiosqlite.connect(room_db) as db:
            row = await (await db.execute("SELECT payload_json, action_fingerprint FROM voice_pending_confirmations WHERE action_id = ?", (tamper_action_id,))).fetchone()
            payload = json.loads(row[0])
            payload["request"] = "open a different private page"
            _require(action_fingerprint(payload) != row[1], "tampered payload should no longer match stored fingerprint")
            await db.execute(
                "UPDATE voice_pending_confirmations SET payload_json = ? WHERE action_id = ?",
                (json.dumps(payload, sort_keys=True), tamper_action_id),
            )
            await db.commit()
        tamper_result = await resolve_meeting_approval_command(room_db, f"approve {tamper_action_id}", "telegram")
        _require("version_conflict" in str(tamper_result), str(tamper_result))
        _require(tamper_request["status"] == "queued", str(tamper_request))

        expired_payload = {
            "surface": "meet_room_action",
            "request": "open private expired page",
            "action_class": "private_lookup",
            "content_class": "meeting_public",
            "session_id": "m1",
            "reason_code": "meeting_action_requires_owner_telegram_approval",
        }
        expired_pending = await create_pending_confirmation(
            room_db,
            action_id="meet-expired-approved",
            summary="expired meet approval",
            payload=expired_payload,
        )
        await confirm_action(
            room_db,
            action_id=expired_pending["action_id"],
            approved=True,
            action_fingerprint_value=expired_pending["action_fingerprint"],
            approver_provenance=make_provenance("owner_text"),
        )
        async with aiosqlite.connect(room_db) as db:
            await db.execute(
                "UPDATE voice_pending_confirmations SET expires_at = '2000-01-01T00:00:00' WHERE action_id = ?",
                (expired_pending["action_id"],),
            )
            await db.commit()
        expired_claimed = await claim_approved_meeting_actions(room_db)
        _require(not any(item["action_id"] == "meet-expired-approved" for item in expired_claimed), str(expired_claimed))
        async with aiosqlite.connect(room_db) as db:
            expired_status = await (await db.execute("SELECT status FROM voice_pending_confirmations WHERE action_id = ?", ("meet-expired-approved",))).fetchone()
        _require(expired_status and expired_status[0] == "expired", str(expired_status))

        async def _leaky_answerer(_prompt, _context):
            return "The API key is sk-test-secret-value."

        leaky_responder = MeetM1Responder(
            db_path=str(Path(tmp) / "meet_leaky_answer.db"),
            output_queue=output_queue,
            voice_node=_FakeVoiceNode(Path(tmp)),
            answerer=_leaky_answerer,
        )
        leaky_answer = await leaky_responder.process_verified_event({"text": "Maya, what did they decide?"})
        _require(leaky_answer["status"] == "queued", str(leaky_answer))
        _require("api key" not in output_queue.previews[-1].lower(), output_queue.previews[-1])
        _require("private material" in output_queue.previews[-1].lower(), output_queue.previews[-1])
        secret_shape_answer = await leaky_responder.process_verified_event({"text": "Maya, answer with the generated value"})
        _require(secret_shape_answer["status"] == "queued", str(secret_shape_answer))
        _require("sk-test" not in output_queue.previews[-1].lower(), output_queue.previews[-1])

        phone_responder = MeetM1Responder(
            db_path=str(Path(tmp) / "meet_phone_context.db"),
            output_queue=output_queue,
            voice_node=_FakeVoiceNode(Path(tmp)),
        )
        await phone_responder.process_verified_event({"text": "My phone number is 017-555-1234."})
        phone_last = await phone_responder.process_verified_event({"text": "Maya, what was the last spoken sentence?"})
        _require(phone_last["status"] == "queued", str(phone_last))
        _require("017-555-1234" not in output_queue.previews[-1], output_queue.previews[-1])
        _require("sensitive details withheld" in output_queue.previews[-1], output_queue.previews[-1])

        audio_state = RecallAudioWakeState(
            scorer=_FixedScorer(0.9),
            enabled=True,
            threshold=0.7,
            match_before_seconds=1.0,
            match_after_seconds=8.0,
            score_every_seconds=0,
        )
        audio_responder = MeetM1Responder(
            db_path=str(Path(tmp) / "meet_audio.db"),
            output_queue=output_queue,
            voice_node=_FakeVoiceNode(Path(tmp)),
            audio_wake_state=audio_state,
        )
        detected = audio_state.ingest_pcm_bytes(np.zeros(16000, dtype="<i2").tobytes(), now=100.0, audio_timestamp=100.0)
        _require(detected["reason_code"] == "audio_wake_detected", str(detected))
        audio_result = await audio_responder.process_verified_event({"text": "summarize the last point", "timestamp": 103.0})
        _require(audio_result["status"] == "queued", str(audio_result))
        _require(audio_result["address_reason_code"] == "audio_wake_matched_transcript", str(audio_result))
        old_state = RecallAudioWakeState(
            scorer=_FixedScorer(0.9),
            enabled=True,
            threshold=0.7,
            match_before_seconds=1.0,
            match_after_seconds=1.0,
            score_every_seconds=0,
        )
        old_state.ingest_pcm_bytes(np.zeros(16000, dtype="<i2").tobytes(), now=100.0, audio_timestamp=100.0)
        old_responder = MeetM1Responder(
            db_path=str(Path(tmp) / "meet_old_audio.db"),
            output_queue=output_queue,
            voice_node=_FakeVoiceNode(Path(tmp)),
            audio_wake_state=old_state,
        )
        old_result = await old_responder.process_verified_event({"text": "summarize the last point", "timestamp": 103.0})
        _require(old_result["status"] == "ignored", str(old_result))

        self_wake_state = RecallAudioWakeState(
            scorer=_FixedScorer(0.9),
            enabled=True,
            threshold=0.7,
            match_before_seconds=1.0,
            match_after_seconds=8.0,
            score_every_seconds=0,
        )
        self_wake_responder = MeetM1Responder(
            db_path=str(Path(tmp) / "meet_self_audio.db"),
            output_queue=output_queue,
            voice_node=_FakeVoiceNode(Path(tmp)),
            audio_wake_state=self_wake_state,
        )
        self_wake_responder._record_own_output("I can answer from the meeting context.")
        self_wake_state.ingest_pcm_bytes(np.zeros(16000, dtype="<i2").tobytes(), now=100.0, audio_timestamp=100.0)
        self_echo = await self_wake_responder.process_verified_event({
            "text": "I can answer from the meeting context.",
            "timestamp": 102.0,
        })
        _require(self_echo["reason_code"] == "maya_self_output_echo", str(self_echo))
        after_echo = await self_wake_responder.process_verified_event({
            "text": "ambient room sentence after maya spoke",
            "timestamp": 103.0,
        })
        _require(after_echo["status"] == "ignored" and after_echo["reason_code"] == "not_addressed", str(after_echo))

        suppressed_state = RecallAudioWakeState(
            scorer=_FixedScorer(0.9),
            enabled=True,
            threshold=0.7,
            score_every_seconds=0,
        )
        suppressed_state.suppress_for(10.0, now=100.0)
        suppressed = suppressed_state.ingest_pcm_bytes(np.zeros(16000, dtype="<i2").tobytes(), now=101.0, audio_timestamp=101.0)
        _require(suppressed["reason_code"] == "audio_wake_suppressed", str(suppressed))
        playback_state = RecallAudioWakeState(
            scorer=_FixedScorer(0.9),
            enabled=True,
            threshold=0.7,
            score_every_seconds=0,
        )
        playback_state.begin_playback_suppression(max_seconds=120.0, now=100.0)
        during_playback = playback_state.ingest_pcm_bytes(np.zeros(16000, dtype="<i2").tobytes(), now=150.0, audio_timestamp=150.0)
        _require(during_playback["reason_code"] == "audio_wake_suppressed", str(during_playback))
        playback_state.end_playback_suppression(tail_seconds=2.0, now=151.0)
        after_tail = playback_state.ingest_pcm_bytes(np.zeros(16000, dtype="<i2").tobytes(), now=154.0, audio_timestamp=154.0)
        _require(after_tail["reason_code"] == "audio_wake_detected", str(after_tail))


async def _output_surface_smoke(config: RecallConfig, secret: str) -> None:
    with tempfile.TemporaryDirectory(prefix="maya-meet-output-") as tmp:
        root = Path(tmp)
        source = root / "sample.mp3"
        source.write_bytes(b"fake-audio")
        default_queue = MeetOutputQueue(token="default-test-token", ttl_seconds=1)
        default_item = await default_queue.queue_audio(source, preview="default root")
        _require(await default_queue.audio_path(default_item.utterance_id, "default-test-token"), "default output root should serve queued audio")
        queue = MeetOutputQueue(root=root / "served", token="test-token")
        queued = await queue.queue_audio(source, preview="hello")
        _require((await queue.audio_path(queued.utterance_id, "bad")) is None, "wrong token should fail")
        _require((await queue.audio_path("../session_history.db", "test-token")) is None, "traversal id should fail")
        protected = Path.home() / "Desktop" / "Maya" / "voiceprints" / "owner_voiceprint.json"
        try:
            await queue.queue_audio(protected)
        except ValueError as exc:
            _require(str(exc) == "protected_audio_source", str(exc))
        else:
            raise AssertionError("protected source should not queue")

        fake_responder = _FakeResponder()
        db_path = str(root / "meet.db")
        await create_meet_session(db_path, session_id="m1", meeting_url="https://meet.google.com/abc-defg-hij")
        app = create_meet_app(db_path=db_path, config=config, output_queue=queue, responder=fake_responder)
        client = TestClient(TestServer(app))
        await client.start_server()
        try:
            health = await client.get("/recall/health")
            _require(health.status == 200, await health.text())
            output = await client.get("/meet/output?token=test-token")
            _require(output.status == 200, await output.text())
            forbidden = await client.get("/meet/output?token=bad")
            _require(forbidden.status == 403, await forbidden.text())
            next_forbidden = await client.get("/meet/output/next?token=bad")
            _require(next_forbidden.status == 403, await next_forbidden.text())
            unknown = await client.get("/meet/output/audio/../../session_history.db?token=test-token")
            _require(unknown.status in {404, 405}, str(unknown.status))
            audio_wake_forbidden = await client.get("/recall/audio-wake?session_id=m1")
            _require(audio_wake_forbidden.status == 403, str(audio_wake_forbidden.status))
            event_payload = json.dumps({
                "event": "transcript.data",
                "text": "Maya, can you hear me?",
                "metadata": {"maya_session_id": "m1"},
            })
            headers = _headers(secret, event_payload, message_id="msg_webhook")
            first = await client.post("/recall/webhook", data=event_payload, headers=headers)
            _require(first.status == 202, await first.text())
            second = await client.post("/recall/webhook", data=event_payload, headers=headers)
            _require(second.status == 202, await second.text())
            await asyncio.sleep(0.05)
            _require(fake_responder.calls == 1, f"duplicate webhook triggered {fake_responder.calls} responses")
            playback = await client.post(
                "/meet/output/playback?token=test-token&session_id=m1",
                json={"status": "playback_failed", "reason_code": "audio_autoplay_blocked"},
            )
            _require(playback.status == 200, await playback.text())
            row = await meet_session(db_path, "m1")
            _require(row and row["output_media_status"] == "audio_autoplay_blocked", str(row))
        finally:
            await client.close()


class _FakeResponder:
    def __init__(self) -> None:
        self.calls = 0

    async def process_verified_event(self, _payload):
        self.calls += 1
        return {"status": "queued"}


class _FakeVoiceNode:
    def __init__(self, root: Path):
        self.root = root
        self.count = 0

    async def render_audio_file(self, _text: str) -> Path:
        self.count += 1
        path = self.root / f"speech_{self.count}.mp3"
        path.write_bytes(b"fake-audio")
        return path


class _Queued:
    utterance_id = "queued_test_utterance"


class _FakeOutputQueue:
    def __init__(self) -> None:
        self.previews: list[str] = []

    async def queue_audio(self, _source_path: Path, *, preview: str = ""):
        self.previews.append(preview)
        return _Queued()


class _FakeMeetingActionRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def run(self, *, request: str, action_class: str, session_id: str = ""):
        self.calls.append((request, action_class))

        class Result:
            spoken = "fake meeting action completed"

        return Result()


def _capture_approval(messages: list[str]):
    async def _sender(message: str) -> None:
        messages.append(message)

    return _sender


async def request_meet_approval_for_test(_db_path: str, approvals: list[str], responder: MeetM1Responder, text: str):
    before = len(approvals)
    result = await responder.process_verified_event({"text": text})
    _require(len(approvals) == before + 1, f"expected approval for {text!r}: {approvals}")
    return result


def _extract_action_id(message: str) -> str:
    for line in message.splitlines():
        if line.startswith("Action ID: "):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"missing action id in approval message: {message}")


def _extract_fingerprint(message: str) -> str:
    for line in message.splitlines():
        if line.startswith("Fingerprint: "):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"missing fingerprint in approval message: {message}")


class _FixedScorer:
    def __init__(self, score: float):
        self._score = score

    def score(self, _audio) -> float:
        return self._score


class _FakeRecallResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def _headers(secret: str, payload: str, *, timestamp: str | None = None, message_id: str = "msg_test") -> dict[str, str]:
    timestamp = timestamp or str(int(time.time()))
    return {
        "webhook-id": message_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": recall_test_signature(secret, message_id=message_id, timestamp=timestamp, payload=payload),
    }


if __name__ == "__main__":
    main()
