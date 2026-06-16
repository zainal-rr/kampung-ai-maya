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

from maya_browser.browser_understanding import extract_browser_options_with_gemini
from storage import init_db


async def main() -> None:
    old_key = os.environ.pop("GOOGLE_API_KEY", None)
    try:
        with tempfile.TemporaryDirectory(prefix="maya-browser-understanding-") as tmp:
            db_path = str(Path(tmp) / "smoke.db")
            await init_db(db_path)
            options = await extract_browser_options_with_gemini(
                db_path,
                provider="Booking.com",
                goal="hotel in Penang",
                page_title="Hotels",
                page_url="https://example.test",
                page_text="Hotel A RM300 Hotel B RM420",
            )
            assert options == []
    finally:
        if old_key is not None:
            os.environ["GOOGLE_API_KEY"] = old_key
    print("browser_understanding_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
