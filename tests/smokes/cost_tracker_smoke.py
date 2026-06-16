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

from cost_tracker import record_usage, usage_summary_text
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-cost-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await init_db(db_path)
        await record_usage(db_path, "ara_tts_chars", 1000, "test")
        await record_usage(db_path, "gpt_complex_calls", 2, "test")
        await record_usage(db_path, "claude_steward_calls", 1, "test")
        summary = await usage_summary_text(db_path)
        _require("Ara TTS: 1000 chars" in summary, "Ara usage missing")
        _require("GPT complex: 2 calls" in summary, "complex usage missing")
        _require("Claude steward: 1 calls" in summary, "Claude steward usage missing")
        _require("Total estimate:" in summary, "total estimate missing")
        print("cost_tracker_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
