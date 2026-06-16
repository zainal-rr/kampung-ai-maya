from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
from pathlib import Path

from local_actions import LocalActionRouter
from permission_policy import path_allowed


async def main() -> None:
    bridge = _FakeBridge()
    router = LocalActionRouter(bridge)
    switched = await router.handle("switch to Google Chrome")
    _require("switched" in switched.lower(), "switch app did not route")
    _require(bridge.calls[-1] == ("switch", "Google Chrome"), "switch app parsed the wrong app name")
    alias = await router.handle("switch to chrome")
    _require("Google Chrome" in alias, "switch app did not resolve app alias")
    _require(bridge.calls[-1] == ("switch", "Google Chrome"), "switch app alias sent wrong app name")
    natural = await router.handle("open my chrome")
    _require("Google Chrome" in natural, "natural possessive app phrase did not resolve")
    _require(bridge.calls[-1] == ("switch", "Google Chrome"), "natural possessive sent wrong app name")
    suffix = await router.handle("open chrome in my imac")
    _require("Google Chrome" in suffix, "iMac suffix app phrase did not resolve")
    _require(bridge.calls[-1] == ("switch", "Google Chrome"), "iMac suffix sent wrong app name")
    pronoun = await router.handle("open it in my imac")
    _require("Google Chrome" in pronoun, "app pronoun did not reuse last app")
    _require(bridge.calls[-1] == ("switch", "Google Chrome"), "app pronoun sent wrong app name")
    polite = await router.handle("can you open my chrome please")
    _require("Google Chrome" in polite, "polite app phrase did not resolve")
    _require(bridge.calls[-1] == ("switch", "Google Chrome"), "polite phrase sent wrong app name")
    browser = await router.handle("please open my browser")
    _require("Google Chrome" in browser, "browser alias did not resolve")
    _require(bridge.calls[-1] == ("switch", "Google Chrome"), "browser alias sent wrong app name")
    where = await router.handle("where?")
    _require("Google Chrome" in where, "where follow-up did not use last app")
    pressed = await router.handle("press command l")
    _require("pressed command l" in pressed.lower(), "shortcut did not route")
    typed = await router.handle("type kampung ai")
    _require("typed it" in typed.lower(), "typing did not route")
    _require(path_allowed(Path.home() / "Desktop" / "secret.txt"), "Desktop path was blocked")
    _require(path_allowed(Path.home() / "Documents" / "note.txt"), "Documents path was blocked")
    print("app_interaction_smoke: ok")


class _FakeBridge:
    def __init__(self):
        self.calls = []

    def switch_app(self, name: str):
        self.calls.append(("switch", name))
        return None

    def get_frontmost_app(self):
        return self.calls[-1][1]

    def press_shortcut(self, shortcut: str):
        self.calls.append(("shortcut", shortcut))
        return None

    def type_text(self, text: str):
        self.calls.append(("type", text))
        return None


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
