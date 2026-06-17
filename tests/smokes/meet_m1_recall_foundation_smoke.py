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
from pathlib import Path

from maya_core.provenance import make_provenance, provenance_from_source_channel
from maya_meet.config import RecallConfig
from maya_meet.engagement import addressed_to_maya, strip_maya_address
from maya_meet.policy import meeting_turn_decision
from maya_meet.recall_client import create_bot_payload, create_recall_bot
from maya_meet.recall_events import handle_recall_event
from maya_meet.recall_security import recall_test_signature, verify_recall_signature
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
        rejected = await handle_recall_event(db_path, session_id="m1", secret=secret, headers=bad, raw_payload=payload)
        _require(rejected["status"] == "rejected", str(rejected))
        stale_result = await handle_recall_event(db_path, session_id="m1", secret=secret, headers=stale, raw_payload=payload)
        _require(stale_result["reason_code"] == "signature_timestamp_stale", str(stale_result))
        row = await meet_session(db_path, "m1")
        _require(row and row["room_authority_level"] == "level_0_locked", str(row))

    _require(addressed_to_maya("Maya, what did Amir decide?"), "direct address missed")
    _require(addressed_to_maya("Maya can you summarize the last point?"), "bare direct address missed")
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
    )
    missing = create_recall_bot(config, "https://meet.google.com/abc-defg-hij")
    _require(missing.reason_code == "recall_config_missing", str(missing))
    payload = create_bot_payload(config, "https://meet.google.com/abc-defg-hij")
    _require(payload["output_media"]["camera"]["kind"] == "webpage", str(payload))


def _headers(secret: str, payload: str, *, timestamp: str | None = None) -> dict[str, str]:
    message_id = "msg_test"
    timestamp = timestamp or str(int(time.time()))
    return {
        "webhook-id": message_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": recall_test_signature(secret, message_id=message_id, timestamp=timestamp, payload=payload),
    }


if __name__ == "__main__":
    main()
