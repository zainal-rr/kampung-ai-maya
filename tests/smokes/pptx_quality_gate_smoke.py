from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import os
import tempfile
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.util import Inches

from office_modern_files import create_pptx
from pptx_quality_gate import ensure_pptx_quality, inspect_pptx_quality


def main() -> None:
    old_root = os.environ.get("MAYA_WORKSPACE_ROOT")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        bad = Path(tmp) / "bad.pptx"
        create_pptx(bad, "Placeholder Deck", [("Intro", ["Meta Ray Ban Display visual anchor"])])
        before = inspect_pptx_quality(bad)
        _require(not before.passed, "placeholder deck should fail QA")
        good = Path(tmp) / "good.pptx"
        create_pptx(good, "Router Setup", [
            ("Router Setup", ["WAN planning", "LAN addressing", "Firewall baseline"]),
            ("Implementation", ["Connect uplink", "Create VLANs", "Test failover"]),
        ])
        after = ensure_pptx_quality(good, max_revisions=1)
        _require(after.passed, "normal generated deck should pass QA")
        _require(after.images and all(path.exists() for path in after.images), "QA did not render slides")
        stretched = Path(tmp) / "stretched.pptx"
        square = Path(tmp) / "square.png"
        Image.new("RGB", (512, 512), (30, 60, 90)).save(square)
        create_pptx(stretched, "Seoul Food Trip", [("Seoul Food Trip", ["Anchor meal", "Budget logic"])])
        deck = Presentation(stretched)
        deck.slides[0].shapes.add_picture(str(square), Inches(1), Inches(1), width=Inches(9), height=Inches(2))
        deck.save(stretched)
        stretched_result = inspect_pptx_quality(stretched)
        _require(not stretched_result.passed, "stretched picture should fail QA")
        _require(any("stretched image" in issue for issue in stretched_result.issues), "stretched image issue missing")
    if old_root is None:
        os.environ.pop("MAYA_WORKSPACE_ROOT", None)
    else:
        os.environ["MAYA_WORKSPACE_ROOT"] = old_root
    print("pptx_quality_gate_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
