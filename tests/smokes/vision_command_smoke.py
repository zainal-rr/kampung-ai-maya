from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import json
import os
import tempfile
from pathlib import Path

from maya_core.lesson_store import init_lesson_db
from maya_core.routine_store import init_routine_db
from skill_store import init_skill_db
from storage import init_db, upsert_preference
from maya_core.route_tracker import last_route_text
from telegram_commands import command_to_text, parse_command
from maya_core.assistant import KampungAssistant
from vision_responder import VisionResponder
from vision_service import VisionSnapshot
from vision_session import activate_guided_sight


async def main() -> None:
    os.environ["ENABLE_VISION_CAMERA"] = "1"
    os.environ["MAYA_EYE_PREVIEW"] = "0"
    with tempfile.TemporaryDirectory(prefix="maya-vision-command-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        os.environ["MAYA_EYE_PREVIEW_TARGET_FILE"] = str(Path(tmp) / "target.json")
        await _init(db_path)

        blocked = await VisionResponder(db_path, _FakeCapture(True), _FakeSenses()).handle("which port should I use", "telegram")
        _require(blocked is None, "Guided sight should not run before /see")

        await command_to_text(db_path, parse_command("/see"))
        visible = await VisionResponder(db_path, _FakeCapture(True), _FakeSenses()).handle("which port should I use", "telegram")
        _require("desk and monitor" in visible, "Visible frame was not described")
        _require(not visible.lower().startswith("i see. i see"), "Vision reply repeated I see")
        _require(Path(os.environ["MAYA_EYE_PREVIEW_TARGET_FILE"]).exists(), "Preview target was not written")

        await activate_guided_sight(db_path)
        _require(not Path(os.environ["MAYA_EYE_PREVIEW_TARGET_FILE"]).exists(), "New /see did not clear old target")
        multi = await VisionResponder(db_path, _FakeCapture(True), _FakeSenses()).handle("which ports can I use", "telegram")
        _require("ports 1 to 4" in multi, "Multi-port answer was not returned")
        targets = json.loads(Path(os.environ["MAYA_EYE_PREVIEW_TARGET_FILE"]).read_text(encoding="utf-8"))
        _require(len(targets["targets"]) == 4, "Multiple usable ports were not all targeted")

        await activate_guided_sight(db_path)
        shape = await VisionResponder(db_path, _FakeCapture(True), _FakeSenses()).handle("what shape is this router", "telegram")
        _require("rectang" in shape.lower(), "Shape answer was not returned")
        _require(not Path(os.environ["MAYA_EYE_PREVIEW_TARGET_FILE"]).exists(), "Shape answer should not leave a target")

        unreadable = await VisionResponder(db_path, _FakeCapture(True), _FakeSenses()).handle("what router model is this", "telegram")
        _require("can't read the label" in unreadable.lower(), "Unreadable label answer was not returned")
        _require(not Path(os.environ["MAYA_EYE_PREVIEW_TARGET_FILE"]).exists(), "Unreadable label should not leave a target")

        await upsert_preference(
            db_path,
            "maya_eye_orientation",
            "for the desk setup, mouse is on Zainal's right and curtain or fabric is on Zainal's left",
            source="test",
        )
        oriented = await VisionResponder(db_path, _FakeCapture(True), _FakeSenses()).handle("where is the button", "telegram")
        _require("calibrated orientation received" in oriented, "Orientation rule was not added to vision prompt")
        _require("zainal's side" in _FakeSenses.last_prompt.lower(), "User perspective instruction was not added")

        no_sight = await VisionResponder(db_path, _FakeCapture(False), _FakeSenses()).handle("can you see", "telegram")
        _require("can't see right now" in no_sight, "No sight status was not reported")

        toggled_off = await command_to_text(db_path, parse_command("/see"))
        _require("stopped seeing" in toggled_off, "/see did not toggle off")
        blocked_again = await VisionResponder(db_path, _FakeCapture(True), _FakeSenses()).handle("which port should I use", "telegram")
        _require(blocked_again is None, "Guided sight stayed active after /see toggle off")
        assistant = KampungAssistant(db_path)
        assistant.vision_responder = VisionResponder(db_path, _FakeCapture(True), _FakeSenses())
        off_reply = await assistant.handle_text("what do you see", "telegram")
        _require("Use /see first" in off_reply, "Vision off-state did not ask for permission")
        route = await last_route_text(db_path)
        _require("camera sight state" in route and "cost recorded: no" in route, "Vision off-state route was wrong")

        status = await command_to_text(db_path, parse_command("/status"))
        _require("privacy block closed" in status, "Vision status was not recorded")

        print("vision_command_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)


class _FakeCapture:
    def __init__(self, visible: bool):
        self.visible = visible

    def capture_once(self) -> VisionSnapshot:
        if self.visible:
            return VisionSnapshot(True, "visible", b"fake-jpeg")
        return VisionSnapshot(False, "Cisco Desk Camera 4K privacy block closed or no visible frame.")


class _FakeSenses:
    last_prompt = ""

    async def describe_image(self, image_bytes: bytes, prompt: str) -> str:
        _FakeSenses.last_prompt = prompt
        if "which ports can i use" in prompt.lower():
            return (
                "You can use LAN ports 1 to 4.\n"
                "TARGET: LAN 1, 500, 500, 45\n"
                "TARGET: LAN 2, 450, 500, 45\n"
                "TARGET: LAN 3, 400, 500, 45\n"
                "TARGET: LAN 4, 350, 500, 45"
            )
        if "what shape is this router" in prompt.lower():
            return "It is rectangular.\nTARGET: router body, 500, 500, 250"
        if "router model" in prompt:
            return "I can't read the label clearly from this angle.\nTARGET: label, 500, 500, 80"
        if "mouse is on Zainal's right" in prompt:
            return "calibrated orientation received. I see a desk and monitor in front of me.\nTARGET: button, 510, 440, 70"
        if "private document" not in prompt:
            return "missing private document guard"
        return "I see a desk and monitor in front of me.\nTARGET: port, 500, 500, 80"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
