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

from maya_core.channel_adapters import adapter_for, all_adapters
from maya_core.channel_gateway import channel_envelope, remember_channel_identity
from storage import get_preference, init_db


async def main() -> None:
    adapters = {item.channel_id: item for item in all_adapters()}
    for channel in ("telegram", "imac", "omi", "mudra", "future_message"):
        _require(channel in adapters, f"{channel} adapter missing")
    _require(adapters["telegram"].can_send_text and adapters["telegram"].can_send_files, "Telegram delivery flags wrong")
    _require(adapters["imac"].can_speak and adapters["imac"].can_show_local_app_or_screen, "iMac flags wrong")
    _require(not adapters["omi"].can_send_text and not adapters["mudra"].can_speak, "passive adapters too active")
    envelope = adapter_for("telegram").envelope("hello", attachments=("a.docx",))  # type: ignore[union-attr]
    _require(envelope["privacy_level"] == "personal_remote", "privacy level missing")
    _require(channel_envelope("telegram", "hi")["text"] == "hi", "gateway envelope failed")
    with tempfile.TemporaryDirectory(prefix="maya-channel-adapter-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await remember_channel_identity(db_path, "telegram", "123")
        _require(await get_preference(db_path, "telegram_chat_id") == "123", "channel identity not saved via gateway")
    print("channel_adapter_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
