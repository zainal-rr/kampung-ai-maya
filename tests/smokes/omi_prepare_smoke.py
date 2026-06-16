from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import json
import tempfile
from pathlib import Path

from omi_adapter import load_omi_transcript


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "omi.json"
        path.write_text(
            json.dumps({
                "text": "Discussed router setup",
                "timestamp": "2026-05-19T12:00:00+08:00",
                "confidence": 0.91,
                "device_id": "pending-omi",
            }),
            encoding="utf-8",
        )
        transcript = load_omi_transcript(path)
        _require(transcript.text == "Discussed router setup", "text missing")
        _require(transcript.confidence == 0.91, "confidence missing")
        _require(transcript.device_id == "pending-omi", "device id missing")
    print("omi_prepare_smoke: ok")


if __name__ == "__main__":
    main()
