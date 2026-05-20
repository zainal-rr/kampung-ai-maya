from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

from lesson_store import init_lesson_db
from routine_store import init_routine_db
from skill_store import init_skill_db
from storage import init_db, upsert_preference
from telegram_commands import command_to_text, parse_command
from vision_responder import VisionResponder
from vision_service import VisionSnapshot


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
        _require(Path(os.environ["MAYA_EYE_PREVIEW_TARGET_FILE"]).exists(), "Preview target was not written")

        await command_to_text(db_path, parse_command("/see"))
        _require(not Path(os.environ["MAYA_EYE_PREVIEW_TARGET_FILE"]).exists(), "New /see did not clear old target")
        multi = await VisionResponder(db_path, _FakeCapture(True), _FakeSenses()).handle("which ports can I use", "telegram")
        _require("ports 1 to 4" in multi, "Multi-port answer was not returned")
        targets = json.loads(Path(os.environ["MAYA_EYE_PREVIEW_TARGET_FILE"]).read_text(encoding="utf-8"))
        _require(len(targets["targets"]) == 4, "Multiple usable ports were not all targeted")

        await command_to_text(db_path, parse_command("/see"))
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
        return "I see a desk and monitor in front of me.\nTARGET: port, 500, 500, 80"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
