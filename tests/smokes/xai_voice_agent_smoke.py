from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from maya_voice.xai_voice_agent import (
    conversation_item_payload,
    input_audio_append_payload,
    input_audio_commit_payload,
    realtime_url,
    response_create_payload,
    session_update_payload,
)


def main() -> None:
    url = realtime_url()
    _require("grok-voice-latest" in url, "default voice model alias missing")
    session = session_update_payload()["session"]
    _require(session["voice"] == "ara", "Ara voice is not the default")
    _require(session["turn_detection"]["type"] is None, "manual turn detection not configured")
    item = conversation_item_payload("hello")
    _require(item["item"]["content"][0]["text"] == "hello", "text item payload failed")
    audio = input_audio_append_payload(b"abc")
    _require(audio["type"] == "input_audio_buffer.append", "audio append payload failed")
    _require(input_audio_commit_payload()["type"] == "input_audio_buffer.commit", "audio commit payload failed")
    response = response_create_payload()
    _require("audio" in response["response"]["modalities"], "audio response not requested")
    print("xai_voice_agent_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
