from __future__ import annotations

import base64
from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class PlaybackCommand:
    type: str
    audio: bytes = b""


class SessionCloseReason(str, Enum):
    RUNNING = "running"
    MANUAL_STOP = "manual_stop"
    IDLE = "idle"
    WEBSOCKET_TIMEOUT = "websocket_timeout"
    INPUT_ERROR = "input_error"
    AUDIO_ERROR = "audio_error"
    TOOL_ERROR = "tool_error"
    ERROR = "error"
    COMPLETED = "completed"


def _decode_audio_delta(event: dict) -> bytes:
    return base64.b64decode(event.get("delta", ""))
