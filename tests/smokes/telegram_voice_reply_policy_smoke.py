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

from assistant import KampungAssistant
import telegram_channel
from storage import init_db
from telegram_delivery_state import save_last_voice_message_id
from telegram_channel import TelegramChannel
import telegram_delivery


class FakeBot:
    def __init__(self):
        self.text_sent = False
        self.voice_sent = False
        self.audio_sent = False
        self.documents = []
        self.deleted = []
        self.next_message_id = 100

    async def send_message(self, **kwargs):
        self.text_sent = True

    async def send_voice(self, **kwargs):
        self.voice_sent = True
        message_id = self.next_message_id
        self.next_message_id += 1
        return FakeMessage(message_id)

    async def send_audio(self, **kwargs):
        self.audio_sent = True
        message_id = self.next_message_id
        self.next_message_id += 1
        return FakeMessage(message_id)

    async def send_document(self, chat_id: int, document, caption: str | None = None, **kwargs):
        self.documents.append({"chat_id": chat_id, "caption": caption})

    async def delete_message(self, **kwargs):
        self.deleted.append(kwargs["message_id"])


class FakeMessage:
    def __init__(self, message_id: int):
        self.message_id = message_id


class FakeVoice:
    def __init__(self, path: Path):
        self.path = path
        self.cleaned = False
        self.last_text = ""

    async def render_audio_file(self, text: str):
        self.last_text = text
        self.path.write_bytes(b"mp3")
        return self.path

    async def cleanup_file(self, audio_path: Path):
        self.cleaned = True


async def main() -> None:
    os.environ["TELEGRAM_VOICE_REPLIES"] = "1"
    os.environ["TELEGRAM_VOICE_LOCKED"] = "1"
    os.environ["TELEGRAM_SEND_VOICE_NOTE"] = "1"
    os.environ["TELEGRAM_VOICE_INCLUDE_TEXT"] = "0"
    os.environ["XAI_API_KEY"] = "test-key"
    os.environ["TELEGRAM_ALLOWED_CHAT_IDS"] = "1"
    with tempfile.TemporaryDirectory(prefix="maya-telegram-voice-policy-") as tmp:
        db_path = str(Path(tmp) / "test.db")
        await init_db(db_path)
        channel = TelegramChannel("dummy", KampungAssistant(db_path))
        channel.assistant.voice = FakeVoice(Path(tmp) / "channel-speech.mp3")
        assert await channel._should_send_voice("voice note") is True
        assert await channel._should_send_voice("text") is False
        assert await channel._should_send_voice("command") is False
        assert await channel._should_send_voice("voice error") is False
        bot = FakeBot()
        audio_path = Path(tmp) / "speech.mp3"
        voice_note_path = Path(tmp) / "speech.ogg"
        voice_note_path.write_bytes(b"ogg")
        old_voice_note_path = telegram_delivery._voice_note_path
        telegram_delivery._voice_note_path = lambda path: _return(voice_note_path)
        try:
            long_voice = FakeVoice(audio_path)
            long_text = (
                "First sentence is short. "
                "Second sentence carries the actual explanation about quantum spin and context. "
                "Third sentence should still be included in the Telegram voice note."
            )
            await telegram_delivery.send_speech(bot, 1, long_voice, long_text)
        finally:
            telegram_delivery._voice_note_path = old_voice_note_path
        assert bot.voice_sent is True
        assert bot.audio_sent is False
        assert "Second sentence carries" in long_voice.last_text
        assert "Third sentence should still be included" in long_voice.last_text
        spoken = telegram_delivery._telegram_voice_text(
            "1) First answer.\n"
            "a) It should not read like a document.\n"
            "**Good:** speak naturally."
        )
        assert "1)" not in spoken
        assert "a)" not in spoken
        assert "**" not in spoken
        assert "First answer" in spoken
        assert "speak naturally" in spoken
        voice_only_bot = FakeBot()
        await save_last_voice_message_id(db_path, 1, 42)
        old_send_speech = telegram_channel.send_speech
        telegram_channel.send_speech = _fake_send_speech
        try:
            await channel._send_response(FakeUpdate(), FakeContext(voice_only_bot), "I am here.", "voice note")
        finally:
            telegram_channel.send_speech = old_send_speech
        assert voice_only_bot.text_sent is False
        assert voice_only_bot.voice_sent is True
        assert voice_only_bot.deleted == [42]
        file_bot = FakeBot()
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        attached = Path(os.environ["MAYA_WORKSPACE_ROOT"]) / "documents" / "result.docx"
        attached.parent.mkdir(parents=True)
        attached.write_bytes(b"docx")
        old_send_speech = telegram_channel.send_speech
        telegram_channel.send_speech = _fake_send_speech
        try:
            await channel._send_response(
                FakeUpdate(),
                FakeContext(file_bot),
                f"Done. I created a Word draft.\n[file:{attached}]",
                "voice note",
            )
        finally:
            telegram_channel.send_speech = old_send_speech
        assert file_bot.text_sent is False
        assert file_bot.voice_sent is True
        assert len(file_bot.documents) == 1
        summary_bot = FakeBot()
        summary_voice = FakeVoice(Path(tmp) / "summary-speech.mp3")
        channel.assistant.voice = summary_voice
        old_send_speech = telegram_channel.send_speech
        telegram_channel.send_speech = telegram_delivery.send_speech
        old_voice_note_path = telegram_delivery._voice_note_path
        telegram_delivery._voice_note_path = lambda path: _return(Path(tmp) / "summary-speech.ogg")
        (Path(tmp) / "summary-speech.ogg").write_bytes(b"ogg")
        try:
            await channel._send_response(
                FakeUpdate(),
                FakeContext(summary_bot),
                f"Last document: {attached}\nSummary: Word document about a two day Kyoto trip.\n[file:{attached}]",
                "voice note",
            )
        finally:
            telegram_channel.send_speech = old_send_speech
            telegram_delivery._voice_note_path = old_voice_note_path
        assert "Word document about a two day Kyoto trip" in summary_voice.last_text
        assert str(attached) not in summary_voice.last_text
        failed_bot = FakeBot()
        old_transcribe = telegram_channel.transcribe_telegram_voice
        telegram_channel.transcribe_telegram_voice = _raise_transcription_error
        try:
            await channel.handle_voice_message(FakeUpdate(), FakeContext(failed_bot))
        finally:
            telegram_channel.transcribe_telegram_voice = old_transcribe
        assert failed_bot.text_sent is True
        assert failed_bot.voice_sent is False
        assert failed_bot.audio_sent is False
    print("telegram_voice_reply_policy_smoke: ok")


async def _return(value):
    return value


async def _raise_transcription_error(*args):
    raise RuntimeError("simulated STT failure")


async def _fake_send_speech(bot, chat_id, voice, text):
    return await bot.send_voice(chat_id=chat_id, voice=b"fake")


class FakeChat:
    id = 1


class FakeUpdate:
    effective_chat = FakeChat()


class FakeContext:
    def __init__(self, bot):
        self.bot = bot


if __name__ == "__main__":
    asyncio.run(main())
