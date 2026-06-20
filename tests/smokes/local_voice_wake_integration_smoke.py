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

from maya_core.local_voice_channel import LocalVoiceChannel
from maya_core.storage import init_db


class FakeSource:
    def __init__(self, items):
        self.items = list(items)

    async def listen(self) -> str:
        return self.items.pop(0) if self.items else "exit"


class FakeVoice:
    def __init__(self):
        self.spoken: list[str] = []

    async def speak(self, text: str) -> None:
        self.spoken.append(text)


class FakeAssistant:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.voice = FakeVoice()
        self.handled: list[tuple[str, str, bool]] = []

    async def handle_text(self, text: str, channel: str = "imac", speak_reply: bool = False) -> str:
        self.handled.append((text, channel, speak_reply))
        return "handled"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def main() -> None:
    old_voice = os.environ.get("ENABLE_XAI_VOICE_AGENT")
    os.environ["ENABLE_XAI_VOICE_AGENT"] = "0"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = f"{tmp}/voice.sqlite"
            await init_db(db_path)
            assistant = FakeAssistant(db_path)
            channel = LocalVoiceChannel(
                assistant,
                transcript_source=FakeSource(["exit"]),
                wake_source=FakeSource(["Maya"]),
            )
            await channel.run()
            _require(assistant.voice.spoken == ["I'm here."], "wake did not acknowledge locally")
            _require(not assistant.handled, "wake-only turn should not call assistant text lane")
            _require(not channel.voice_agent.active, "Grok voice agent should stay off")
    finally:
        if old_voice is None:
            os.environ.pop("ENABLE_XAI_VOICE_AGENT", None)
        else:
            os.environ["ENABLE_XAI_VOICE_AGENT"] = old_voice
    print("local_voice_wake_integration_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
