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

from activation import WakeWindow, mudra_is_near, split_wake_phrase, wake_phrases
from mudra_adapter import load_mudra_event
from omi_adapter import load_omi_transcript
from permission_policy import permission_summary


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-hardware-ready-") as tmp:
        root = Path(tmp)
        txt = root / "omi.txt"
        js = root / "omi.json"
        mudra = root / "mudra.json"
        txt.write_text("Omi transcript text", encoding="utf-8")
        js.write_text(json.dumps({"transcript": "Omi JSON text"}), encoding="utf-8")
        mudra.write_text(json.dumps({"gesture": "double_pinch", "wearing": True, "distance_m": 0.7}), encoding="utf-8")

        _require(load_omi_transcript(txt).text == "Omi transcript text", "Omi txt parse failed")
        _require(load_omi_transcript(js).text == "Omi JSON text", "Omi json parse failed")
        event = load_mudra_event(mudra)
        _require(event.gesture == "double_pinch" and mudra_is_near(event.wearing, event.distance_m), "Mudra parse failed")
        _require("hey maya" in wake_phrases(), "wake phrase missing")
        woke, command = split_wake_phrase("Hey Maya check my day")
        _require(woke and command == "check my day", "wake split failed")
        window = WakeWindow(seconds=5)
        _require(window.apply("Hello Maya")[0] and window.apply("continue")[0], "wake window failed")
        _require("Sensitive private exposure is blocked" in permission_summary(), "permission summary missing boundary")
        print("hardware_readiness_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
