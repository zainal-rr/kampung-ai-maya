from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import numpy as np
import cv2

from maya_core.vision_markup import draw_visual_marks, parse_targets, should_group_targets


def main() -> None:
    text = (
        "TARGET: LAN 1, 500, 500, 45\n"
        "TARGET: LAN 2, 450, 500, 45\n"
        "TARGET: LAN 3, 400, 500, 45\n"
        "TARGET: LAN 4, 350, 500, 45"
    )
    targets = parse_targets(text)
    _require(len(targets) == 4, "Multiple target lines were not parsed")
    _require(should_group_targets(targets), "Close targets should group into one area")

    separated = [("left", 100, 100, 40), ("middle", 500, 500, 40), ("right", 900, 900, 40)]
    _require(not should_group_targets(separated), "Separated targets should stay separate")

    image = np.zeros((300, 500, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", image)
    _require(ok, "Test image encoding failed")
    path = draw_visual_marks(encoded.tobytes(), targets)
    _require(path is not None and path.exists(), "Grouped target image was not written")
    path.unlink(missing_ok=True)

    print("vision_markup_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
