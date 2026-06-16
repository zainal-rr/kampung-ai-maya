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

from PIL import Image
from pptx import Presentation

import pptx_visual_assets
from office_modern_files import create_pptx
from pptx_visual_assets import add_gemini_visual_asset, topic_benefits_from_visuals, visual_image_cap


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-pptx-visual-") as tmp:
        root = Path(tmp)
        deck = create_pptx(
            root / "seoul.pptx",
            "2-day Seoul food trip",
            [
                ("Seoul Food Trip", ["Plan meals."]),
                ("Food Highlights", ["Myeongdong Kyoja", "Gwangjang Market"]),
                ("Route Logic", ["Cluster stops", "Keep backup meals"]),
            ],
        )
        old_enabled = os.environ.get("ENABLE_PPTX_GEMINI_IMAGES")
        old_google = os.environ.get("GOOGLE_API_KEY")
        old_workspace = os.environ.get("MAYA_WORKSPACE_ROOT")
        os.environ["ENABLE_PPTX_GEMINI_IMAGES"] = "1"
        os.environ["GOOGLE_API_KEY"] = "fake"
        os.environ["MAYA_WORKSPACE_ROOT"] = str(root / "Maya")
        old_generate = pptx_visual_assets.generate_gemini_image
        pptx_visual_assets.generate_gemini_image = _fake_generate
        try:
            added, note = await add_gemini_visual_asset(deck, "2-day Seoul food trip")
        finally:
            pptx_visual_assets.generate_gemini_image = old_generate
            if old_enabled is None:
                os.environ.pop("ENABLE_PPTX_GEMINI_IMAGES", None)
            else:
                os.environ["ENABLE_PPTX_GEMINI_IMAGES"] = old_enabled
            if old_google is None:
                os.environ.pop("GOOGLE_API_KEY", None)
            else:
                os.environ["GOOGLE_API_KEY"] = old_google
            if old_workspace is None:
                os.environ.pop("MAYA_WORKSPACE_ROOT", None)
            else:
                os.environ["MAYA_WORKSPACE_ROOT"] = old_workspace
        _require(added, note)
        _require(visual_image_cap(10) == 13, "10-slide image cap should be ceil(13.0)")
        _require(visual_image_cap(4) == 6, "4-slide image cap should round 5.2 up to 6")
        _require(topic_benefits_from_visuals("Seoul food trip"), "food trip should trigger visuals")
        _require(not topic_benefits_from_visuals("plain internal notes"), "plain notes should not trigger visuals")
        pptx = Presentation(deck)
        pictures = [shape for slide in pptx.slides for shape in slide.shapes if getattr(shape, "shape_type", None) == 13]
        image_count = len(pictures)
        _require(image_count >= 3, "Gemini visuals were not inserted across the deck")
        _require(
            any(
                max(p.crop_left, p.crop_right, p.crop_top, p.crop_bottom) > 0
                for p in pictures
            ),
            "Gemini visuals should use crop metadata instead of stretching into mismatched frames",
        )
    print("pptx_visual_assets_smoke: ok")


async def _fake_generate(prompt: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1280, 720), (231, 241, 235)).save(path)
    return path


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
