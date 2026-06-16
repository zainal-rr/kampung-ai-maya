from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import tempfile
from pathlib import Path

import telegram_voice_input as voice_input
from cost_tracker import usage_summary_text
from storage import init_db


class FakeAttachment:
    file_id = "voice-file"
    duration = 12


class FakeMessage:
    voice = FakeAttachment()
    audio = None


class FakeUpdate:
    message = FakeMessage()


class FakeTelegramFile:
    async def download_to_drive(self, custom_path: str) -> None:
        Path(custom_path).write_bytes(b"fake audio")


class FakeBot:
    async def get_file(self, file_id: str):
        return FakeTelegramFile()


class FakeContext:
    bot = FakeBot()


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-voice-input-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)

        async def fake_convert(input_path, wav_path):
            wav_path.write_bytes(b"fake wav")

        async def fake_transcribe(wav_path):
            return "hello maya", True

        old_convert = voice_input._convert_to_wav
        old_transcribe = voice_input._transcribe_wav
        voice_input._convert_to_wav = fake_convert
        voice_input._transcribe_wav = fake_transcribe
        try:
            text = await voice_input.transcribe_telegram_voice(FakeUpdate(), FakeContext(), db_path)
        finally:
            voice_input._convert_to_wav = old_convert
            voice_input._transcribe_wav = old_transcribe

        _require(text == "hello maya", "voice note was not transcribed")
        summary = await usage_summary_text(db_path)
        _require("0.2 min" in summary, "voice note STT usage was not tracked")
        print("telegram_voice_input_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
