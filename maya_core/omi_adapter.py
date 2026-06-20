from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OmiTranscript:
    text: str
    source_name: str
    source_tag: str
    timestamp: str = ""
    confidence: float | None = None
    device_id: str = ""
    ingestion_status: str = "loaded"


def load_omi_transcript(path: str | Path) -> OmiTranscript:
    file_path = Path(path)
    raw = file_path.read_text(encoding="utf-8").strip()
    if file_path.suffix.lower() == ".json":
        data = json.loads(raw or "{}")
        text = (
            str(data.get("text") or data.get("transcript") or data.get("content") or "")
            .strip()
        )
        timestamp = str(data.get("timestamp") or data.get("created_at") or "")
        confidence = _optional_float(data.get("confidence"))
        device_id = str(data.get("device_id") or data.get("device") or "")
    else:
        text = raw
        timestamp = ""
        confidence = None
        device_id = ""
    return OmiTranscript(
        text=text,
        source_name=file_path.name,
        source_tag=f"source:{file_path.name}",
        timestamp=timestamp,
        confidence=confidence,
        device_id=device_id,
    )


def _optional_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
