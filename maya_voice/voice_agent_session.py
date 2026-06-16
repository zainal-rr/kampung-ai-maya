from __future__ import annotations

import os
import time
from collections.abc import Callable

from cost_tracker import record_usage
from route_tracker import record_route
from xai_voice_agent import XaiRealtimeVoiceAgentTransport


class StubVoiceAgentTransport:
    speaks_for_itself = False

    def __init__(self):
        self.messages: list[str] = []
        self.opened = False

    async def open(self) -> None:
        self.opened = True

    async def send_text(self, text: str) -> str:
        self.messages.append(text)
        return f"Voice agent stub handled: {text}"

    async def send_audio(self, audio: bytes) -> str:
        self.messages.append(f"audio:{len(audio)}")
        return f"Voice agent audio stub handled {len(audio)} bytes"

    async def close(self) -> None:
        self.opened = False


class GrokVoiceAgentSession:
    def __init__(
        self,
        db_path: str,
        transport_factory: Callable[[], object] | None = None,
        now: Callable[[], float] | None = None,
        idle_seconds: int | None = None,
    ):
        self.db_path = db_path
        self.transport_factory = transport_factory or _transport_factory
        self.now = now or time.monotonic
        self.idle_seconds = idle_seconds or int(os.getenv("XAI_VOICE_AGENT_IDLE_SECONDS", "20"))
        self.transport = None
        self.started_at = 0.0
        self.last_activity = 0.0

    @property
    def enabled(self) -> bool:
        return os.getenv("ENABLE_XAI_VOICE_AGENT", "0") == "1"

    @property
    def active(self) -> bool:
        return self.transport is not None

    @property
    def speaks_for_itself(self) -> bool:
        return bool(getattr(self.transport, "speaks_for_itself", False))

    async def start(self) -> None:
        if not self.enabled or self.active:
            return
        self.transport = self.transport_factory()
        await self.transport.open()
        self.started_at = self.now()
        self.last_activity = self.started_at
        await record_route(self.db_path, "voice", "Grok Voice Agent", "wake phrase", False)

    async def handle_text(self, text: str) -> str:
        await self.start()
        if not self.transport:
            return ""
        self.last_activity = self.now()
        return await self.transport.send_text(text)

    async def handle_audio(self, audio: bytes) -> str:
        await self.start()
        if not self.transport:
            return ""
        self.last_activity = self.now()
        return await self.transport.send_audio(audio)

    async def close_if_idle(self) -> bool:
        if self.active and self.now() - self.last_activity >= self.idle_seconds:
            await self.close("idle timeout")
            return True
        return False

    async def close(self, reason: str = "closed") -> None:
        if not self.transport:
            return
        duration = max(0.0, self.now() - self.started_at)
        transport = self.transport
        self.transport = None
        await transport.close()
        await record_usage(self.db_path, "grok_voice_agent_seconds", duration, reason)
        await record_route(self.db_path, "voice", "Grok Voice Agent", reason, duration > 0)


def build_voice_agent_session(db_path: str) -> GrokVoiceAgentSession:
    return GrokVoiceAgentSession(db_path)


def _transport_factory():
    if os.getenv("XAI_VOICE_AGENT_MODE", "stub") == "real":
        return XaiRealtimeVoiceAgentTransport()
    return StubVoiceAgentTransport()
