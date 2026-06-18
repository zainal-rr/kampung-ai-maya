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

from aiohttp.test_utils import TestClient, TestServer

from maya_core.provenance import make_provenance, provenance_from_source_channel
from maya_meet.config import RecallConfig
from maya_meet.engagement import addressed_to_maya, strip_maya_address
from maya_meet.output_media import MeetOutputQueue
from maya_meet.policy import meeting_turn_decision
from maya_meet.recall_client import create_bot_payload, create_recall_bot
from maya_meet.recall_events import handle_recall_event
from maya_meet.recall_security import recall_test_signature, verify_recall_signature
from maya_meet.service import _maya_session_id, create_meet_app
from maya_meet.store import create_meet_session, meet_session


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

    _require(addressed_to_maya("Maya, what did Amir decide?"), "direct address missed")
    _require(addressed_to_maya("Maya can you summarize the last point?"), "bare direct address missed")
    _require(addressed_to_maya("Hey, Maya, summarize that"), "punctuated greeting address missed")
    _require(strip_maya_address("Hey Maya, summarize that") == "summarize that", "address strip failed")
    _require(not addressed_to_maya("I was telling Maya about the project"), "casual mention should not engage")
    _require(not addressed_to_maya("Maya is already in the meeting notes"), "sentence reference should not engage")

    other = provenance_from_source_channel("meeting_speech")
    _require(other.source_kind == "other_speaker", "meeting speech must not become owner")
    ignored = meeting_turn_decision(text="please summarize", provenance=other)
    _require(ignored.status == "ignored", str(ignored))
    answer = meeting_turn_decision(text="Maya, summarize the last point", provenance=other)
    _require(answer.status == "answer_allowed", str(answer))
    blocked = meeting_turn_decision(text="Maya, open the browser", provenance=other, action_class="lookup")
    _require(blocked.reason_code == "meeting_other_speaker_cannot_act", str(blocked))
    private = meeting_turn_decision(text="Maya, read my private notes", provenance=other, content_class="owner_private")
    _require(private.reason_code == "owner_private_disclosure_blocked", str(private))
    owner_m1 = meeting_turn_decision(text="Maya, open the agenda", provenance=make_provenance("owner_voice_meeting"), action_class="lookup")
    _require(owner_m1.reason_code == "meeting_m2_disabled", str(owner_m1))

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
    nested = {
        "data": {
            "bot": {"metadata": {"maya_session_id": "bot_session"}},
            "recording": {"metadata": {"maya_session_id": "recording_session"}},
        }
    }
    _require(_maya_session_id(nested) == "bot_session", "bot metadata session not found")
    await _output_surface_smoke(config, secret)


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
