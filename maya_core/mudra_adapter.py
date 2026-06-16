from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from maya_core.hardware_event_store import record_hardware_event


logger = logging.getLogger("maya.mudra")


@dataclass(frozen=True)
class MudraEvent:
    gesture: str
    channel: str = "imac"
    wearing: bool = False
    distance_m: float | None = None
    source_device: str = "mudra_link_pending"


def load_mudra_event(path: str | Path) -> MudraEvent:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return MudraEvent(
        gesture=str(payload.get("gesture") or payload.get("event") or "").strip().lower(),
        channel=str(payload.get("channel") or "imac").strip().lower(),
        wearing=bool(payload.get("wearing") or payload.get("worn") or False),
        distance_m=_optional_float(payload.get("distance_m") or payload.get("distance")),
        source_device=str(payload.get("source_device") or payload.get("device") or "mudra_link_pending"),
    )


class MudraAdapter:
    def __init__(self, assistant, event_dir: str):
        self.assistant = assistant
        self.event_dir = Path(event_dir)
        self.event_dir.mkdir(parents=True, exist_ok=True)
        self.poll_seconds = 3

    async def run(self) -> None:
        logger.info("Mudra adapter recording prepared-only events from %s", self.event_dir)
        while True:
            for file_path in sorted(self.event_dir.glob("*.json")):
                await self._process(file_path)
            await asyncio.sleep(self.poll_seconds)

    async def _process(self, file_path: Path) -> None:
        try:
            event = load_mudra_event(file_path)
            logger.info("Mudra event recorded without action mapping: %s", event.gesture)
            await record_hardware_event(
                self.assistant.db_path,
                source="mudra",
                event_type=event.gesture or "unknown",
                payload={
                    "gesture": event.gesture,
                    "channel": event.channel,
                    "wearing": event.wearing,
                    "distance_m": event.distance_m,
                    "source_device": event.source_device,
                },
                status="prepared_only",
            )
        except Exception as exc:
            logger.exception("Mudra event processing failed: %s", exc)
        finally:
            if file_path.exists():
                file_path.unlink()

def _optional_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
