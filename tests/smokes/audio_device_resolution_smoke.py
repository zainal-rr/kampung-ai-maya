from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from maya_core.audio_devices import list_audio_devices, resolve_audio_input


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    _require(resolve_audio_input(":5") == ":5", "colon index did not pass through")
    _require(resolve_audio_input("5") == ":5", "numeric index did not normalize")
    devices = list_audio_devices()
    if devices:
        first = devices[0]
        _require(resolve_audio_input(first.name) == first.ffmpeg_input, "name did not resolve")
    print("audio_device_resolution_smoke: ok")


if __name__ == "__main__":
    main()
