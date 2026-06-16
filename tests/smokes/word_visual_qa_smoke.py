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

from maya_documents.office_modern_files import create_docx
from word_visual_qa import inspect_word_visual_quality


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-word-visual-") as tmp:
        root = Path(tmp)
        good = create_docx(
            root / "good.docx",
            "Router Setup Guide",
            [
                ("Purpose", ["Set up a router with secure admin access, internet connectivity, and recoverable settings."]),
                ("Configuration Steps", ["Change the admin password, configure WAN, set SSID, enable WPA2 or WPA3, and save the configuration."]),
                ("Verification", ["Confirm WAN IP, DNS, WiFi login, and browsing from a client device."]),
            ],
        )
        good_qa = inspect_word_visual_quality(good)
        _require(not good_qa.issues, f"good Word visual QA should pass: {good_qa.issues}")

        long_paragraph = " ".join(["This visually dense paragraph makes the Word layout hard to scan."] * 18)
        weak = create_docx(
            root / "weak.docx",
            "A Very Long Heading That Makes The Document Feel Like A Wall Of Text Before The Reader Even Starts",
            [("Overview", [long_paragraph])],
        )
        weak_qa = inspect_word_visual_quality(weak)
        _require(any("too long" in issue or "visually dense" in issue for issue in weak_qa.issues), f"weak visual issue missing: {weak_qa.issues}")
    print("word_visual_qa_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
