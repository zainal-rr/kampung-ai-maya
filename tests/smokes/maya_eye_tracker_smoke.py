from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import numpy as np

from maya_core.maya_eye_tracker import TargetTracker


def main() -> None:
    tracker = TargetTracker()
    target = {"label": "router port", "x": 500, "y": 500, "radius": 80}

    first = _frame_with_square(100, 100)
    seeded = tracker.update(first, target)
    _require(seeded is not None, "Tracker did not seed the first target")

    moved = _frame_with_square(150, 120)
    tracked = tracker.update(moved, target)
    _require(tracked is not None, "Tracker did not follow the moved target")
    _, x, y, _ = tracked
    _require(abs(x - 150) < 16 and abs(y - 120) < 16, "Tracker followed the wrong position")

    missing = tracker.update(np.zeros((220, 220, 3), dtype=np.uint8), target)
    _require(missing is None, "Tracker should hide target when it disappears")

    returned = tracker.update(moved, target)
    _require(returned is not None, "Tracker did not reacquire the returned target")

    print("maya_eye_tracker_smoke: ok")


def _frame_with_square(x: int, y: int):
    frame = np.zeros((220, 220, 3), dtype=np.uint8)
    frame[y - 24 : y + 24, x - 24 : x + 24] = (255, 255, 255)
    frame[y - 12 : y + 12, x - 12 : x + 12] = (20, 20, 20)
    return frame


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
