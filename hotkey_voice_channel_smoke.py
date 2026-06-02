import asyncio
import os
import tempfile
from pathlib import Path

from hotkey_voice_channel import HotkeyVoiceChannel
from storage import get_preference, init_db, upsert_preference
from voice_agent_audio import VoiceAgentAudioCapture, _pcm16_rms
from xai_voice_handoff import VOICE_HANDOFF_KEY, save_voice_handoff_request


class FakeVoice:
    def __init__(self):
        self.spoken = []

    async def speak(self, text):
        self.spoken.append(text)


class FakeVoiceAgent:
    enabled = True

    def __init__(self):
        self.active = True
        self.texts = []
        self.audio_turns = 0
        self.closed = []
        self.idle_checks = 0

    async def handle_text(self, text):
        self.texts.append(text)
        return "I'm here."

    async def start(self):
        self.active = True

    async def handle_audio(self, audio):
        self.audio_turns += 1
        return "handled audio"

    async def close_if_idle(self):
        if not self.active:
            return False
        self.idle_checks += 1
        self.active = False
        self.closed.append("idle timeout")
        return True

    async def close(self, reason):
        self.active = False
        self.closed.append(reason)


class FakeAudioCapture:
    def __init__(self, clips):
        self.clips = list(clips)

    async def listen_audio(self):
        return self.clips.pop(0) if self.clips else b""


class StopAfterFirstCapture(FakeAudioCapture):
    def __init__(self, channel):
        super().__init__([b"1234"])
        self.channel = channel

    async def listen_audio(self):
        self.channel.stop_requested = True
        return await super().listen_audio()


class FakeAssistant:
    def __init__(self, db_path):
        self.db_path = db_path
        self.voice = FakeVoice()
        self.handled = []

    async def handle_text(self, text, channel, speak_reply=False):
        self.handled.append((text, channel, speak_reply))
        return "handled handoff"


async def main():
    os.environ["MAYA_HOTKEY_VOICE_MODE"] = "diagnostic"
    os.environ["MAYA_ENABLE_DIAGNOSTIC_FFMPEG_CAPTURE"] = "1"
    tmp = tempfile.TemporaryDirectory(prefix="maya-hotkey-smoke-")
    db_path = str(Path(tmp.name) / "smoke.db")
    await init_db(db_path)
    assistant = FakeAssistant(db_path)
    channel = HotkeyVoiceChannel(assistant, audio_capture=FakeAudioCapture([b"1234", b""]))
    channel.voice_agent = FakeVoiceAgent()
    await channel._run_voice_session()
    assert channel.voice_agent.texts == []
    assert channel.voice_agent.audio_turns == 1
    assert channel.voice_agent.closed == ["idle timeout"]
    assert channel.session_active is False
    stop_channel = HotkeyVoiceChannel(assistant, audio_capture=FakeAudioCapture([]))
    stop_channel.voice_agent = FakeVoiceAgent()
    await upsert_preference(db_path, "maya_active_workflow", "browser:search:test", source="test")
    await save_voice_handoff_request(db_path, "make an Excel file that should be cancelled")
    await stop_channel.stop_voice_session()
    assert stop_channel.voice_agent.closed == ["manual hotkey stop"]
    assert await get_preference(db_path, "maya_active_workflow") is None
    assert await get_preference(db_path, VOICE_HANDOFF_KEY) is None
    assert not assistant.handled
    await save_voice_handoff_request(db_path, "make a Word document about routers")
    await stop_channel._run_pending_voice_handoff()
    assert assistant.handled[-1] == ("make a Word document about routers", "imac", True)
    interrupted = HotkeyVoiceChannel(assistant)
    interrupted.voice_agent = FakeVoiceAgent()
    interrupted.audio_capture = StopAfterFirstCapture(interrupted)
    await interrupted._run_voice_session()
    assert interrupted.voice_agent.audio_turns == 0
    assert "manual hotkey stop" in interrupted.voice_agent.closed
    assert _pcm16_rms(b"\0\0" * 2000) == 0
    capture = VoiceAgentAudioCapture(min_rms=180)
    capture._record_pcm = fake_record_silence
    assert await capture.listen_audio() == b""
    tmp.cleanup()
    print("hotkey_voice_channel_smoke: ok")


async def fake_record_silence(path):
    path.write_bytes(b"\0\0" * 2000)


if __name__ == "__main__":
    asyncio.run(main())
