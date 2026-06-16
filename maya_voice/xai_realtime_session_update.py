from __future__ import annotations

import os

from xai_realtime_tools import voice_tools


def session_update_payload(instructions: str, sample_rate: int) -> dict:
    silence_ms = int(os.getenv("XAI_VOICE_TURN_SILENCE_MS", "2200"))
    return {
        "type": "session.update",
        "session": {
            "voice": os.getenv("XAI_VOICE_AGENT_VOICE", "ara"),
            "instructions": instructions,
            "input_audio_transcription": {"model": os.getenv("XAI_VOICE_TRANSCRIPTION_MODEL", "grok-2-audio")},
            "turn_detection": {"type": "server_vad", "silence_duration_ms": silence_ms, "prefix_padding_ms": 500},
            "tools": voice_tools(),
            "audio": {
                "input": {"format": {"type": "audio/pcm", "rate": sample_rate}},
                "output": {"format": {"type": "audio/pcm", "rate": sample_rate}},
            },
        },
    }
