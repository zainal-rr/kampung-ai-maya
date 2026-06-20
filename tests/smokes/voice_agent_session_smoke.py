from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import os
import tempfile
from pathlib import Path

from maya_core.cost_tracker import usage_summary_text
from maya_core.route_tracker import last_route_text
from maya_core.storage import init_db
from maya_voice.voice_agent_session import GrokVoiceAgentSession, StubVoiceAgentTransport


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def now(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


async def main() -> None:
    old_enabled = os.environ.get("ENABLE_XAI_VOICE_AGENT")
    old_idle = os.environ.get("XAI_VOICE_AGENT_IDLE_SECONDS")
    os.environ["ENABLE_XAI_VOICE_AGENT"] = "1"
    os.environ["XAI_VOICE_AGENT_IDLE_SECONDS"] = "5"
    try:
        await _run()
    finally:
        _restore("ENABLE_XAI_VOICE_AGENT", old_enabled)
        _restore("XAI_VOICE_AGENT_IDLE_SECONDS", old_idle)


async def _run() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-voice-agent-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        clock = FakeClock()
        session = GrokVoiceAgentSession(
            db_path,
            transport_factory=StubVoiceAgentTransport,
            now=clock.now,
        )
        reply = await session.handle_text("hello")
        _require(session.active, "voice agent did not start")
        _require("hello" in reply, "stub did not handle text")
        audio_reply = await session.handle_audio(b"audio-bytes")
        _require("audio stub" in audio_reply, "stub did not handle speech audio")
        route = await last_route_text(db_path)
        _require("wake phrase" in route, "start route was not recorded")

        clock.advance(4)
        closed = await session.close_if_idle()
        _require(not closed and session.active, "session closed too early")

        clock.advance(2)
        closed = await session.close_if_idle()
        _require(closed and not session.active, "session did not close after idle")
        summary = await usage_summary_text(db_path)
        _require("Grok Voice Agent: 0.1 min" in summary, "voice agent usage was not tracked")
        route = await last_route_text(db_path)
        _require("cost recorded: yes" in route, "close route did not record cost flag")
        print("voice_agent_session_smoke: ok")


def _restore(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
