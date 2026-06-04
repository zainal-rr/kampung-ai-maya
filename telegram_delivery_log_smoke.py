from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from storage import init_db
from telegram_delivery_log import latest_telegram_delivery_text, record_telegram_delivery


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
