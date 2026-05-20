from __future__ import annotations

import asyncio

from web_actions import WebActionRouter


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
