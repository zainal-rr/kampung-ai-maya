from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

from storage import upsert_preference


logger = logging.getLogger("maya.camera")


@dataclass(frozen=True)
class CameraEvent:
    state: str
    camera_index: int | None = None
    source: str = "external"


def load_camera_event(path: str | Path) -> CameraEvent:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return CameraEvent(
        state=str(payload.get("state") or payload.get("event") or "").strip().lower(),
        camera_index=_optional_int(payload.get("camera_index") or payload.get("index")),
        source=str(payload.get("source") or "external").strip().lower(),
    )


def is_allowed_external_camera(event: CameraEvent) -> bool:
    external_index = int(os.getenv("MAYA_EXTERNAL_CAMERA_INDEX", "0"))
    imac_index = int(os.getenv("MAYA_IMAC_CAMERA_INDEX", "1"))
    if event.camera_index == imac_index and os.getenv("MAYA_DISABLE_IMAC_CAMERA", "1") == "1":
        return False
    if event.camera_index is None:
        return event.source in {"external", "external_camera"}
    return event.camera_index == external_index


class ExternalCameraAdapter:
    def __init__(self, assistant, event_dir: str):
        self.assistant = assistant
        self.event_dir = Path(event_dir)
        self.event_dir.mkdir(parents=True, exist_ok=True)
        self.poll_seconds = 3
        self.active = False

    async def run(self) -> None:
        logger.info("External camera adapter monitoring %s", self.event_dir)
        while True:
            for file_path in sorted(self.event_dir.glob("*.json")):
                await self._process(file_path)
            await asyncio.sleep(self.poll_seconds)

    async def _process(self, file_path: Path) -> None:
        try:
            event = load_camera_event(file_path)
            if event.state in {"open", "active", "on"} and is_allowed_external_camera(event):
                await self._activate()
            elif event.state in {"closed", "inactive", "off"}:
                self.active = False
        except Exception as exc:
            logger.exception("External camera event processing failed: %s", exc)
        finally:
            if file_path.exists():
                file_path.unlink()

    async def _activate(self) -> None:
        await upsert_preference(self.assistant.db_path, "work_location", "imac", source="external_camera")
        if not self.active:
            self.active = True
            await self.assistant.voice.speak("I'm here.")


def _optional_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
