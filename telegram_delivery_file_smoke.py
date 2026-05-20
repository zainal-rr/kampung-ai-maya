from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from telegram_delivery import MAX_TELEGRAM_TEXT, send_text, split_file_markers


class FakeBot:
    def __init__(self):
        self.messages = []
        self.documents = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))

    async def send_document(self, chat_id: int, document, caption: str | None = None) -> None:
        self.documents.append((chat_id, document.name, caption))


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
        await send_text(bot, 123, text)
        _require(bot.messages == [(123, "Here is the file.")], "message delivery failed")
        _require(len(bot.documents) == 1, "document was not delivered")
        _require(bot.documents[0][2] == "maya-notes.docx", "document caption was not set")

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
