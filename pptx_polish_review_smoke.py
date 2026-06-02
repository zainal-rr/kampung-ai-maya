from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches

from pptx_polish_review import _parse_polish, local_polish_issues


def main() -> None:
    old_root = os.environ.get("MAYA_WORKSPACE_ROOT")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        deck = Path(tmp) / "polish.pptx"
        _create_bad_visible_deck(deck)
        issues = local_polish_issues(deck)
        _require(any("incomplete sentence" in issue for issue in issues), "incomplete sentence not detected")
        _require(any("repeats slide titles" in issue for issue in issues), "repeated title not detected")
        _require(_parse_polish('{"grade":"draft-level","reason":""}')[0] == "good", "empty draft-level review should not block after local QA")
        _require(_parse_polish('{"grade":"draft-level","reason":"Slide 2 has incomplete text."}')[0] == "draft-level", "actionable draft-level review should block")
    if old_root is None:
        os.environ.pop("MAYA_WORKSPACE_ROOT", None)
    else:
        os.environ["MAYA_WORKSPACE_ROOT"] = old_root
    print("pptx_polish_review_smoke: ok")


def _create_bad_visible_deck(path: Path) -> None:
    deck = Presentation()
    for _ in range(2):
        slide = deck.slides.add_slide(deck.slide_layouts[6])
        title = slide.shapes.add_textbox(Inches(0.7), Inches(0.5), Inches(7), Inches(0.5))
        title.text_frame.text = "Quantum computing is real"
        body = slide.shapes.add_textbox(Inches(0.7), Inches(1.5), Inches(7), Inches(0.8))
        body.text_frame.text = "NIST is already standardizing post-quantum cryptography in"
    deck.save(path)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
