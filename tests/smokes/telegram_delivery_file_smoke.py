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

from maya_telegram.telegram_delivery import MAX_TELEGRAM_TEXT, send_text, split_file_markers


class FakeBot:
    def __init__(self):
        self.messages = []
        self.documents = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))

    async def send_document(self, chat_id: int, document, caption: str | None = None, **kwargs) -> None:
        self.documents.append((chat_id, document.name, caption))


class FailingBot(FakeBot):
    async def send_document(self, chat_id: int, document, caption: str | None = None, **kwargs) -> None:
        raise TimeoutError("simulated upload timeout")


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-telegram-file-") as root:
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(root) / "Maya")
        allowed_root = Path(os.environ["MAYA_WORKSPACE_ROOT"])
        allowed_root.mkdir(parents=True, exist_ok=True)
        tmp = allowed_root / "artifacts"
        tmp.mkdir()
        path = Path(tmp) / "maya-notes.docx"
        path.write_bytes(b"fake-docx")
        text = f"Here is the file.\n[file:{path}]"
        clean, files = split_file_markers(text)
        _require(clean == "Here is the file.", "file marker was not removed from visible text")
        _require(files == [path.resolve()], "file marker path was not parsed")

        bot = FakeBot()
        events = await send_text(bot, 123, text)
        _require(bot.messages == [(123, "Here is the file.")], "message delivery failed")
        _require(len(bot.documents) == 1, "document was not delivered")
        _require(bot.documents[0][2] == "maya-notes.docx", "document caption was not set")
        _require(any(item["kind"] == "document" and item["status"] == "sent" for item in events), "delivery event did not record sent document")

        failing_bot = FailingBot()
        failed_events = await send_text(failing_bot, 124, text)
        _require(
            any("Telegram upload timed out or failed" in message for _, message in failing_bot.messages),
            "upload failure should send a visible fallback path message",
        )
        _require(any(item["status"] == "failed" for item in failed_events), "delivery event did not record failed upload")

        long_bot = FakeBot()
        await send_text(long_bot, 456, "x" * (MAX_TELEGRAM_TEXT + 50))
        _require(len(long_bot.messages) == 2, "long Telegram text was not chunked")

    with tempfile.TemporaryDirectory(prefix="maya-telegram-blocked-") as tmp:
        blocked_path = Path(tmp) / "secret.txt"
        blocked_path.write_text("secret", encoding="utf-8")
        clean, files = split_file_markers(f"Blocked\n[file:{blocked_path}]")
        _require(clean == "Blocked", "blocked marker should still be stripped")
        _require(files == [], "disallowed file marker should not produce a sendable file")
        docs_dir = Path(tmp) / "docs"
        docs_dir.mkdir()
        docs_secret = docs_dir / "secret.txt"
        docs_secret.write_text("secret", encoding="utf-8")
        _, docs_files = split_file_markers(f"Blocked\n[file:{docs_secret}]")
        _require(docs_files == [], "random docs folder should not be sendable")
        print("telegram_delivery_file_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
