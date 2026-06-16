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

from maya_core.assistant import KampungAssistant
from maya_core.lesson_store import init_lesson_db
from routine_store import init_routine_db
from screen_responder import ScreenResponder
from screen_service import ScreenSnapshot
from skill_store import init_skill_db
from storage import get_preference, init_db
from telegram_commands import command_to_text, parse_command


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-screen-command-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)

        context = _FakeContext()
        responder = ScreenResponder(db_path, _FakeScreen(True), _FakeSenses(), context)
        blocked = await responder.handle("what is on my screen", "telegram")
        _require("Screen sight is off" in blocked, "Telegram screen question should not fall through when /screen is off")
        blocked_doing = await responder.handle("what am i doing on screen now", "telegram")
        _require("Screen sight is off" in blocked_doing, "Doing-on-screen question should need /screen first")
        blocked_followup = await responder.handle("Do I have Codex open?", "telegram")
        _require(blocked_followup is None, "Screen follow-up should need /screen first")

        activated = await command_to_text(db_path, parse_command("/screen"))
        _require(activated == "I can see your screen now.", "/screen did not activate screen sight")
        visible = await responder.handle("what is on my screen", "telegram")
        _require("Quarterly slide" in visible, "Screen was not described after /screen")
        _require("current iMac screen" in _FakeSenses.last_prompt, "Current screen boundary was missing")
        presence = await responder.handle("are you there", "telegram")
        _require(presence is None, "Presence checks should not trigger screen status")
        apps = await responder.handle("What apps is open?", "telegram")
        _require("Open apps from macOS" in apps and "Safari" in apps, "Open app question did not use macOS state")
        visible_apps = await responder.handle("what app is visible now?", "telegram")
        _require("Visible apps from macOS" in visible_apps, "Visible app question did not use macOS state")
        _require("Codex" in visible_apps and "Telegram" in visible_apps, "Visible app state missed expected apps")
        codex_open = await responder.handle("Is Codex open?", "telegram")
        _require("Codex is open" in codex_open, "Named app open question did not use macOS state")
        codex_limit = await responder.handle("Is Codex reaching its limit?", "telegram")
        _require("Codex" in codex_limit, "Active screen session missed app-specific follow-up")
        fallback = await ScreenResponder(db_path, _FakeScreen(True), _FailingSenses(), context).handle(
            "Is Codex reaching its limit?",
            "telegram",
        )
        _require("Codex is open" in fallback and "vision model is unavailable" in fallback, "Vision failure fallback was not useful")
        safari = await responder.handle("Can you see what is in Safari? Do I have Codex open?", "telegram")
        _require("Safari" in safari and "Codex" in safari, "Named app screen question was not answered")
        _require("never say you can only see chat text" in _FakeSenses.last_prompt, "Screen prompt missed denial guard")

        mapped = await command_to_text(db_path, parse_command("/screen explain this diagram"))
        _require(mapped == "look at my screen: explain this diagram", "/screen args did not map")
        assistant = KampungAssistant(db_path)
        assistant.screen_responder = ScreenResponder(db_path, _FakeScreen(True), _FakeSenses(), context)
        routed = await assistant.handle_text("What apps is open?", "telegram")
        _require("Open apps from macOS" in routed, "Assistant route did not prefer screen app state")
        followup = await assistant.handle_text("should I put this information here", "telegram")
        _require("Quarterly slide" in followup, "Persistent screen follow-up did not use fresh screen sight")
        closed = await ScreenResponder(db_path, _FakeScreen(True), _FakeSenses(), _FakeClosedSafari()).handle(
            "What about Safari?",
            "telegram",
        )
        _require("Safari is not open" in closed, "Closed named app was not answered from app state")
        off = await command_to_text(db_path, parse_command("/screen off"))
        _require("Use /screen to toggle" in off, "/screen off should point to toggle")
        still_on = await responder.handle("what about now", "telegram")
        _require("Quarterly slide" in still_on, "/screen off should not deactivate anymore")
        toggled_off = await command_to_text(db_path, parse_command("/screen"))
        _require("stopped looking" in toggled_off, "/screen did not toggle off")
        stopped = await responder.handle("what about now", "telegram")
        _require("Screen sight is off" in stopped, "Screen follow-up should not fall through after toggle off")
        imac = await ScreenResponder(db_path, _FakeScreen(True), _FakeSenses(), context).handle("look at my screen", "imac")
        _require("Quarterly slide" in imac, "iMac screen sight did not work naturally")

        no_screen = await ScreenResponder(db_path, _FakeScreen(False), _FakeSenses()).handle("look at my screen", "imac")
        _require("can't see your screen" in no_screen, "Blocked screen capture was not reported")
        status = await get_preference(db_path, "maya_screen_last_status")
        _require("Screen Recording permission" in status, "Screen status was not stored")
        print("screen_command_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)


class _FakeScreen:
    def __init__(self, visible: bool):
        self.visible = visible

    def capture_once(self) -> ScreenSnapshot:
        if self.visible:
            return ScreenSnapshot(True, "screen visible", b"fake-screen")
        return ScreenSnapshot(False, "Screen Recording permission is blocked for this runtime.")


class _FakeSenses:
    last_prompt = ""

    async def describe_image(self, image_bytes: bytes, prompt: str) -> str:
        _FakeSenses.last_prompt = prompt
        lowered = prompt.lower()
        if "user request: what apps is open" in lowered:
            if "running apps from os" not in prompt.lower():
                return "missing app state\nCONFIDENCE: 10"
            return "Visible apps: Safari, Telegram, and Codex.\nCONFIDENCE: 82"
        if "user request: can you see what is in safari" in lowered:
            if "screen was captured after bringing this app forward: Safari" not in prompt:
                return "Safari is open but not visible.\nCONFIDENCE: 70"
            return "Safari is visible with a browser page open. Codex is also visible.\nCONFIDENCE: 84"
        if "user request: is codex reaching its limit" in lowered:
            return "Codex is visible and appears close to its context limit.\nCONFIDENCE: 82"
        return "Quarterly slide is open with a simple growth diagram.\nCONFIDENCE: 88"


class _FailingSenses:
    async def describe_image(self, image_bytes: bytes, prompt: str) -> str:
        raise RuntimeError("vision unavailable")


class _FakeContext:
    async def prepare(self, request: str):
        from screen_context import ScreenContext

        if "safari" in request.lower():
            return ScreenContext(
                frontmost="Codex",
                running_apps=("Codex", "Safari", "Telegram"),
                requested_app="Safari",
                resolved_app="Safari",
                focused_app="Safari",
            )
        if "codex" in request.lower():
            return ScreenContext(
                frontmost="Codex",
                running_apps=("Codex", "Safari", "Telegram"),
                requested_app="Codex",
                resolved_app="Codex",
            )
        return ScreenContext(frontmost="Codex", running_apps=("Codex", "Safari", "Telegram", "Claude"), visible_apps=("Codex", "Telegram"))


class _FakeClosedSafari:
    async def prepare(self, request: str):
        from screen_context import ScreenContext

        return ScreenContext(frontmost="Codex", running_apps=("Codex", "Telegram"), requested_app="Safari")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
