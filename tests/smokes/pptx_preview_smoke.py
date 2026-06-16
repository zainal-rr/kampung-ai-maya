from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import tempfile
from pathlib import Path

from PIL import Image

from office_modern_files import create_pptx
from pptx_preview import powerpoint_contact_sheet


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-pptx-preview-") as tmp:
        path = Path(tmp) / "seoul-food-trip.pptx"
        create_pptx(
            path,
            "Seoul Food Trip",
            [
                ("Seoul Food Trip", ["Food-first route", "48-hour plan"]),
                ("Day 1: Heritage Market", ["Market stop", "Nearby backup"]),
                ("Day 2: Cafe Crawl", ["Cafe route", "BBQ slot"]),
            ],
        )
        preview = powerpoint_contact_sheet(path)
        _require(preview and preview.exists(), "preview contact sheet was not created")
        image = Image.open(preview)
        try:
            _require(image.width > 600 and image.height > 300, "preview contact sheet is too small")
        finally:
            image.close()
    print("pptx_preview_smoke: ok")


def _require(condition, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
