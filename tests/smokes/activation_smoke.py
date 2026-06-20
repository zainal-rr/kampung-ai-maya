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
import time
from pathlib import Path

import numpy as np

os.environ.setdefault("MPLCONFIGDIR", "/tmp/kampung-ai-mpl")

from maya_core.activation import WakeWindow, current_work_location, handle_activation_command, mudra_is_near, split_wake_phrase
from maya_core.camera_adapter import CameraEvent, ExternalCameraAdapter, is_allowed_external_camera, load_camera_event
from maya_core.lesson_store import init_lesson_db
from maya_core.mudra_adapter import MudraEvent
from maya_core.routine_store import init_routine_db
from maya_core.skill_store import init_skill_db
from maya_core.storage import init_db
from maya_core.vision import VisionNode
from maya_core.vision_session import activate_guided_sight, guided_sight_active


async def main() -> None:
    os.environ["MAYA_EYE_PREVIEW"] = "0"
    with tempfile.TemporaryDirectory(prefix="maya-activation-smoke-") as tmp:
        db_path = str(Path(tmp) / "smoke.db")
        os.environ["MAYA_EYE_PREVIEW_TARGET_FILE"] = str(Path(tmp) / "target.json")
        await _init(db_path)

        woke, command = split_wake_phrase("Hey Maya what are my tasks")
        _require(woke and command == "what are my tasks", "wake phrase did not strip command")
        woke, command = split_wake_phrase("Hey, Maya testing")
        _require(woke and command == "testing", "punctuated wake phrase failed")
        woke, command = split_wake_phrase("Good morning Maya what is my briefing")
        _require(woke and command == "what is my briefing", "good morning wake phrase failed")
        woke, command = split_wake_phrase("hello Maya")
        _require(woke and command == "", "hello Maya wake phrase failed")
        woke, command = split_wake_phrase("Maya, what do you see")
        _require(woke and command == "what do you see", "plain Maya wake phrase failed")

        window = WakeWindow(seconds=5)
        active, command = window.apply("Hello Maya")
        _require(active and command == "", "wake-only phrase did not activate")
        active, command = window.apply("what are my tasks")
        _require(active and command == "what are my tasks", "wake window did not keep voice active")
        old_until = window.active_until
        time.sleep(0.01)
        active, command = window.apply("and my routines")
        _require(active and command == "and my routines", "wake window dropped a follow-up")
        _require(window.active_until > old_until, "wake window did not refresh after follow-up")

        reply = await handle_activation_command(db_path, "open Imac")
        _require(reply and await current_work_location(db_path) == "imac", "Telegram iMac activation failed")

        _require(mudra_is_near(True, 0.8), "Mudra proximity should activate within one metre")
        _require(not mudra_is_near(True, 1.2), "Mudra proximity should not activate beyond one metre")
        _require(MudraEvent("presence", wearing=True, distance_m=0.5).wearing, "Mudra event shape failed")

        vision = VisionNode(camera_index=1)
        _require(vision.camera_index == 0, "VisionNode did not reroute away from iMac camera")
        _require(vision._looks_blocked(np.zeros((10, 10, 3), dtype=np.uint8)), "Blocked lens was not detected")
        _require(not vision._looks_blocked(np.full((10, 10, 3), 255, dtype=np.uint8)), "Bright frame was marked blocked")

        camera_event_path = Path(tmp) / "camera.json"
        camera_event_path.write_text('{"state": "open", "camera_index": 0}', encoding="utf-8")
        camera_event = load_camera_event(camera_event_path)
        _require(is_allowed_external_camera(camera_event), "External camera event was rejected")
        _require(not is_allowed_external_camera(CameraEvent("open", camera_index=1)), "iMac camera event was allowed")

        await activate_guided_sight(db_path)
        Path(os.environ["MAYA_EYE_PREVIEW_TARGET_FILE"]).write_text("{}", encoding="utf-8")
        await handle_activation_command(db_path, "close imac")
        _require(await current_work_location(db_path) == "telegram", "Work location reset failed")
        _require(not await guided_sight_active(db_path), "Guided sight was not closed")
        _require(not Path(os.environ["MAYA_EYE_PREVIEW_TARGET_FILE"]).exists(), "Preview target was not cleared")
        fake_assistant = _FakeAssistant(db_path)
        adapter = ExternalCameraAdapter(fake_assistant, str(Path(tmp) / "camera_sync"))
        await adapter._process(camera_event_path)
        _require(await current_work_location(db_path) == "imac", "External camera event did not activate iMac")
        _require(fake_assistant.voice.spoken == ["I'm here."], "External camera activation did not speak")

        print("activation_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class _FakeVoice:
    def __init__(self):
        self.spoken: list[str] = []

    async def speak(self, text: str) -> None:
        self.spoken.append(text)


class _FakeAssistant:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.voice = _FakeVoice()


if __name__ == "__main__":
    asyncio.run(main())
