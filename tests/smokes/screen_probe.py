from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from screen_service import MacScreenService


def main() -> None:
    snapshot = MacScreenService().capture_once()
    print("== Kampung AI Screen Probe ==")
    print(f"screen_visible: {snapshot.visible}")
    print(f"screen_status: {snapshot.status}")
    print(f"image_bytes: {len(snapshot.image_bytes or b'')}")
    if not snapshot.visible:
        print("recommendation: grant Screen Recording permission to the runtime owner.")


if __name__ == "__main__":
    main()
