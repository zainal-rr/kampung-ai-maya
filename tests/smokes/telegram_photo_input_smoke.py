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

from maya_core.storage import init_db
from maya_telegram.telegram_photo_input import describe_telegram_photo


class FakePhoto:
    file_id = "photo-1"


class FakeMessage:
    photo = [FakePhoto()]
    caption = "what is in this image?"


class FakeUpdate:
    effective_message = FakeMessage()
    message = FakeMessage()


class FakeTelegramFile:
    async def download_to_drive(self, custom_path: str) -> None:
        Path(custom_path).write_bytes(b"fake-jpeg-bytes")


class FakeBot:
    async def get_file(self, file_id: str):
        assert file_id == "photo-1"
        return FakeTelegramFile()


class FakeContext:
    bot = FakeBot()


class FakeSenses:
    def __init__(self):
        self.prompt = ""
        self.bytes_seen = b""

    async def describe_image(self, image_bytes: bytes, prompt: str) -> str:
        self.bytes_seen = image_bytes
        self.prompt = prompt
        return "The photo shows a desk setup."


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-telegram-photo-") as tmp:
        db_path = str(Path(tmp) / "test.db")
        await init_db(db_path)
        senses = FakeSenses()
        reply = await describe_telegram_photo(FakeUpdate(), FakeContext(), db_path, senses=senses)
        _require(reply == "The photo shows a desk setup.", "photo reply mismatch")
        _require(senses.bytes_seen == b"fake-jpeg-bytes", "photo bytes not passed to vision")
        _require("what is in this image?" in senses.prompt, "caption missing from prompt")
        _require("uploaded Telegram photo" in senses.prompt, "Telegram photo boundary missing")
        _require("cannot identify people by face" in senses.prompt, "face identification boundary missing")
        _require("user-provided context" in senses.prompt, "user context boundary missing")
    print("telegram_photo_input_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
