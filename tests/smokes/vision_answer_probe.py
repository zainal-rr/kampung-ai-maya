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

from dotenv import load_dotenv

load_dotenv()
os.environ["ENABLE_VISION_CAMERA"] = "1"

from maya_core.activation import handle_activation_command
from lesson_store import init_lesson_db
from routine_store import init_routine_db
from skill_store import init_skill_db
from storage import init_db
from vision_responder import VisionResponder


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-vision-answer-") as tmp:
        db_path = str(Path(tmp) / "probe.db")
        await _init(db_path)
        await handle_activation_command(db_path, "open imac")
        answer = await VisionResponder(db_path).handle("what do you see", "telegram")
        print("== Kampung AI Vision Answer Probe ==")
        print(answer)


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)


if __name__ == "__main__":
    asyncio.run(main())
