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

import maya_documents.pptx_document_flow as pptx_document_flow
import maya_documents.pptx_visual_assets as pptx_visual_assets
from maya_documents.pptx_document_flow import create_powerpoint_with_qa
from maya_core.storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-pptx-rescue-") as tmp:
        root = Path(tmp)
        db_path = str(root / "test.db")
        await init_db(db_path)
        old_google = os.environ.get("GOOGLE_API_KEY")
        old_enabled = os.environ.get("ENABLE_PPTX_GEMINI_IMAGES")
        old_workspace = os.environ.get("MAYA_WORKSPACE_ROOT")
        old_image = pptx_visual_assets.generate_gemini_image
        old_polish = pptx_document_flow.claude_polish_grade
        os.environ["GOOGLE_API_KEY"] = "fake"
        os.environ["ENABLE_PPTX_GEMINI_IMAGES"] = "1"
        os.environ["MAYA_WORKSPACE_ROOT"] = str(root / "Maya")
        pptx_visual_assets.generate_gemini_image = _fake_generate
        pptx_document_flow.claude_polish_grade = _fake_polish
        try:
            path = root / "seoul-food-trip.pptx"
            qa = await create_powerpoint_with_qa(
                db_path,
                path,
                "Seoul Food Trip Deck",
                [
                    ("Weak Food Deck", ["Avoids dead time when", "Weekend food tour built", "Theme"]),
                    ("Generic Move", ["Key move", "Visual presentation and authentic"]),
                ],
                "smoke",
                "last_doc",
            )
        finally:
            pptx_visual_assets.generate_gemini_image = old_image
            pptx_document_flow.claude_polish_grade = old_polish
            _restore_env("GOOGLE_API_KEY", old_google)
            _restore_env("ENABLE_PPTX_GEMINI_IMAGES", old_enabled)
            _restore_env("MAYA_WORKSPACE_ROOT", old_workspace)
        _require(qa.passed, f"rescue PowerPoint flow should pass: {qa.issues}")
        _require(qa.revisions >= 2, "rescue flow should reach the deterministic rescue attempt")
        deck = Presentation(path)
        text = " ".join(
            " ".join(getattr(shape, "text", "").split())
            for slide in deck.slides
            for shape in slide.shapes
        )
        picture_count = sum(1 for slide in deck.slides for shape in slide.shapes if getattr(shape, "shape_type", None) == 13)
        _require(picture_count >= len(deck.slides), "rescue deck should keep one visual per slide")
        _require("KEY MOVE" not in text and "Avoids Dead Time When" not in text, "rescue deck should remove weak visible labels")
        _require(pptx_document_flow._polish_reason_contains_blocker("Design polish: good. Held back from strong by incomplete fragments like bad text."), "polish blocker text should fail")
        _require(not pptx_document_flow._polish_reason_contains_blocker("Design polish: good. Clear dark visual system."), "clean polish text should pass blocker check")
    print("pptx_rescue_flow_smoke: ok")


async def _fake_generate(prompt: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1280, 720), (34, 42, 58)).save(path)
    return path


async def _fake_polish(db_path: str, path: Path) -> tuple[str, bool]:
    deck = Presentation(path)
    text = " ".join(
        " ".join(getattr(shape, "text", "").split())
        for slide in deck.slides
        for shape in slide.shapes
    )
    # Markers match the current rescue template in pptx_slide_repair
    # AS RENDERED (visual title rewriting keeps these two stable; the old
    # "Save The Splurge For Dinner" marker drifted out of the template).
    if "Seoul In 48 Hours" in text and "Follow The Neighborhood Spine" in text:
        return "Design polish: good. Rescue deck has a clear dark visual system.", False
    return "Design polish: draft-level. Forced first-attempt failure.", False


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
