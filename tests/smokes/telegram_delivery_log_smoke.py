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
from maya_telegram.telegram_delivery_log import latest_telegram_delivery_text, record_telegram_delivery


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-delivery-log-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        empty = await latest_telegram_delivery_text(db_path)
        _require("No Telegram delivery" in empty, "empty delivery state should be explicit")
        await record_telegram_delivery(
            db_path,
            chat_id=123,
            input_type="text",
            status="sent",
            text_chars=40,
            files=[{"kind": "document", "status": "sent", "path": "/Users/zainalabidinjamal/Desktop/Maya/documents/test.docx"}],
        )
        latest = await latest_telegram_delivery_text(db_path)
        _require("Last Telegram delivery:" in latest, "latest delivery header missing")
        _require("status: sent" in latest, "delivery status missing")
        _require("test.docx" in latest, "delivery file path missing")
        print("telegram_delivery_log_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
