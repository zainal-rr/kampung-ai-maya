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
from maya_telegram.telegram_turn_log import latest_telegram_turn_text, record_telegram_turn


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
