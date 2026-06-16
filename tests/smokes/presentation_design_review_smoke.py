from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import os
import tempfile
from pathlib import Path

from office_modern_files import create_pptx
from presentation_design_review import review_presentation_design, wants_presentation_review
from pptx_slide_renderer import render_pptx_slides


async def main() -> None:
    old_root = os.environ.get("MAYA_WORKSPACE_ROOT")
    old_google = os.environ.pop("GOOGLE_API_KEY", None)
    old_anthropic = os.environ.pop("ANTHROPIC_API_KEY", None)
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MAYA_WORKSPACE_ROOT"] = tmp
        deck = Path(tmp) / "presentations" / "meta-ray-ban-display.pptx"
        create_pptx(deck, "Meta Ray-Ban Display", [
            ("Display glasses need a clearer story", ["First point", "Second point"]),
            ("Tradeoffs matter", ["Battery", "Privacy", "Use cases"]),
        ])
        images = render_pptx_slides(deck, Path(tmp) / "screenshots" / "review")
        assert len(images) == 2
        assert all(path.exists() and path.stat().st_size > 1000 for path in images)
        assert wants_presentation_review("review the Meta Ray-Ban Display presentation design")
        reply, cost = await review_presentation_design(str(Path(tmp) / "test.db"), "review the Meta Ray-Ban Display presentation design")
        assert str(deck) in reply
        assert "export slides manually" not in reply.lower()
        assert cost in {True, False}
    if old_root is None:
        os.environ.pop("MAYA_WORKSPACE_ROOT", None)
    else:
        os.environ["MAYA_WORKSPACE_ROOT"] = old_root
    if old_google is not None:
        os.environ["GOOGLE_API_KEY"] = old_google
    if old_anthropic is not None:
        os.environ["ANTHROPIC_API_KEY"] = old_anthropic
    print("presentation_design_review_smoke: ok")


if __name__ == "__main__":
    asyncio.run(main())
