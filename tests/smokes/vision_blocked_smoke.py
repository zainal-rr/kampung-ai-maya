from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import numpy as np

from vision_blocked import frame_blocked


def main() -> None:
    black = np.zeros((20, 20, 3), dtype=np.uint8)
    gray_shutter = np.full((20, 20, 3), 30, dtype=np.uint8)
    bright = np.full((20, 20, 3), 255, dtype=np.uint8)
    textured = np.zeros((20, 20, 3), dtype=np.uint8)
    textured[::2] = 90

    _require(frame_blocked(black), "Black frame should count as blocked")
    _require(frame_blocked(gray_shutter), "Flat low-light shutter frame should count as blocked")
    _require(not frame_blocked(bright), "Bright frame should not count as blocked")
    _require(not frame_blocked(textured), "Textured visible frame should not count as blocked")

    print("vision_blocked_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
