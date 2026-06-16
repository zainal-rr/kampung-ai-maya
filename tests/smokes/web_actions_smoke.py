from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio

from maya_core.web_actions import WebActionRouter


class FakeBridge:
    def __init__(self):
        self.urls: list[str] = []

    def open_url(self, url: str, app_name: str = "Google Chrome") -> None:
        self.urls.append(url)


async def main() -> None:
    bridge = FakeBridge()
    router = WebActionRouter(bridge)

    flight = await router.handle("book me a flight to Penang tomorrow", "telegram")
    _require(flight is not None and "not book or pay" in flight.lower(), "flight guard missing")
    _require("flight" in bridge.urls[-1].lower(), "flight search was not opened")

    web = await router.handle("search the web for kampung ai", "telegram")
    _require(web == "I opened a browser search for that.", "generic web reply wrong")
    _require("kampung+ai" in bridge.urls[-1], "generic web search query wrong")

    ignored = await router.handle("what are my tasks", "telegram")
    _require(ignored is None, "non-web query should be ignored")
    print("web_actions_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
