from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from storage import init_db
from telegram_turn_log import latest_telegram_turn_text, record_telegram_turn


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-turn-log-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        empty = await latest_telegram_turn_text(db_path)
        _require("No Telegram turn" in empty, "empty turn state should be explicit")
        await record_telegram_turn(
            db_path,
            chat_id=123,
            input_type="text",
            prompt="are you there?",
            status="completed",
            duration_ms=321,
            response_chars=9,
            response_preview="yes, I am here",
        )
        latest = await latest_telegram_turn_text(db_path)
        _require("Last Telegram turn:" in latest, "latest turn header missing")
        _require("status: completed" in latest, "turn status missing")
        _require("duration ms: 321" in latest, "turn duration missing")
        _require("response: yes, I am here" in latest, "turn response preview missing")
        print("telegram_turn_log_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
