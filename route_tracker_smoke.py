from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from route_tracker import last_route_text, record_route
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-route-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        empty = await last_route_text(db_path)
        _require(empty == "No route recorded yet.", "empty route text was wrong")
        await record_route(db_path, "voice note", "Kimi coding", "coding question", True)
        text = await last_route_text(db_path)
        _require("voice note" in text, "input type missing")
        _require("Kimi coding" in text, "lane missing")
        _require("cost recorded: yes" in text, "cost flag missing")
        await record_route(db_path, "voice note", "xAI STT + Gemini Flash text", "voice note transcribed, then normal Telegram text", True)
        voice_text = await last_route_text(db_path)
        _require("grok-2-audio" in voice_text and "gemini" in voice_text.lower(), "voice route models missing")
        await record_route(db_path, "text", "Gemini Flash role-based Word draft + local Word QA + Claude Word review", "document workflow", True)
        review_text = await last_route_text(db_path)
        _require("claude-opus-4-8" in review_text, "Claude review routes should default to Opus 4.8")
        print("route_tracker_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
