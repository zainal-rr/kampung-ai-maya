from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from assistant import KampungAssistant
from lesson_store import init_lesson_db
from route_tracker import last_route_text, record_route
from routine_store import init_routine_db
from skill_store import init_skill_db
from storage import init_db
from telegram_channel import TelegramChannel


class FakeBot:
    def __init__(self):
        self.messages: list[str] = []

    async def send_message(self, chat_id: int, text: str):
        self.messages.append(text)


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-route-no-overwrite-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await init_lesson_db(db_path)
        await init_skill_db(db_path)
        await init_routine_db(db_path)
        await record_route(db_path, "text", "Gemini Flash text", "normal Telegram text", True)

        assistant = KampungAssistant(db_path)
        reply = await assistant.handle_text("/route", "telegram")
        _require("Gemini Flash text" in reply, "assistant /route did not show previous route")
        route_after_assistant = await last_route_text(db_path)
        _require("Gemini Flash text" in route_after_assistant, "assistant /route overwrote previous route")

        os.environ["TELEGRAM_ALLOWED_CHAT_IDS"] = "123"
        channel = TelegramChannel("dummy", assistant)
        bot = FakeBot()
        update = SimpleNamespace(
            effective_message=SimpleNamespace(text="/route"),
            effective_chat=SimpleNamespace(id=123),
        )
        context = SimpleNamespace(bot=bot)
        await channel.handle_command(update, context)
        route_after_telegram = await last_route_text(db_path)
        _require("Gemini Flash text" in route_after_telegram, "Telegram /route overwrote previous route")
        _require(bot.messages and "Gemini Flash text" in bot.messages[-1], "Telegram /route did not send last route")
    print("route_no_overwrite_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
