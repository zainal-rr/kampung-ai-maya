from __future__ import annotations

from xai_voice_agent import (
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
