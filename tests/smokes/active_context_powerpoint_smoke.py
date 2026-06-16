from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from pathlib import Path
from tempfile import TemporaryDirectory

from pptx import Presentation

from active_context_document_parsers import parse_powerpoint_context
from active_context_models import ActiveContext
from active_context_powerpoint import verify_powerpoint_visible_context


def main() -> None:
    with TemporaryDirectory(prefix="maya-ppt-visible-") as tmp:
        deck_path = Path(tmp) / "agriculture.pptx"
        deck = Presentation()
        for title, body in (
            ("Agriculture Concerns in Malaysia", "Food security"),
            ("Climate And Flood Exposure", "Flood risk"),
            ("Land Use And Fragmentation", "Fragmented plots make mechanisation and irrigation planning harder"),
        ):
            slide = deck.slides.add_slide(deck.slide_layouts[1])
            slide.shapes.title.text = title
            slide.placeholders[1].text = body
        deck.save(deck_path)
        parsed = parse_powerpoint_context(str(deck_path), 1, "")
        base = ActiveContext(
            app="Microsoft PowerPoint",
            selection_type="powerpoint_selection",
            active_file=str(deck_path),
            active_title=parsed.title,
            nearby_context="slide: 1",
            document_context=parsed.document_context,
            source="powerpoint_applescript_plus_pptx_parser",
        )
        fixed = verify_powerpoint_visible_context(base, "I see slide 3 titled Land Use And Fragmentation.")
        _require(fixed.source == "powerpoint_screen_verified_pptx_parser", "screen verification source missing")
        _require("current_slide: 3" in fixed.document_context, "visible slide did not win")
        _require("slide_match: no" in fixed.nearby_context, "mismatch diagnostic missing")
        _require("Fragmented plots" in fixed.document_context, "visible slide text missing")
    print("active_context_powerpoint_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
