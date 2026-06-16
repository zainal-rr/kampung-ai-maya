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

import maya_documents.pptx_visual_assets as pptx_visual_assets
from maya_documents.pptx_document_flow import create_powerpoint_with_qa
from storage import init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-pptx-multi-visual-") as tmp:
        root = Path(tmp)
        db_path = str(root / "test.db")
        await init_db(db_path)
        old_google = os.environ.get("GOOGLE_API_KEY")
        old_enabled = os.environ.get("ENABLE_PPTX_GEMINI_IMAGES")
        os.environ["GOOGLE_API_KEY"] = "fake"
        os.environ["ENABLE_PPTX_GEMINI_IMAGES"] = "1"
        old_generate = pptx_visual_assets.generate_gemini_image
        pptx_visual_assets.generate_gemini_image = _fake_generate
        try:
            path = root / "seoul-food-trip.pptx"
            qa = await create_powerpoint_with_qa(
                db_path,
                path,
                "Seoul Food Trip Deck",
                [
                    ("Seoul Food Trip", ["Food-first route", "48-hour plan", "Neighborhood clusters"]),
                    ("Daily Anchor", ["Gwangjang Market", "Myeongdong Kyoja", "Cafe route"]),
                    ("Food Highlights", ["Kalguksu", "Bindaetteok", "Korean BBQ"]),
                    ("Budget Logic", ["Market snacks", "Cafe stops", "One splurge meal"]),
                    ("Two Apps That Protect The Plan", ["Naver Maps", "Catchtable", "Reserve early"]),
                    ("Insider Moves That Save The Trip", ["Timing", "Hydration", "BBQ etiquette"]),
                ],
                "smoke",
                "last_doc",
            )
            quality_path = root / "kampung-ai-document-quality.pptx"
            quality_qa = await create_powerpoint_with_qa(
                db_path,
                quality_path,
                "Kampung AI Document Quality",
                [
                    ("Make Artifact Quality Visible", ["Draft", "Build", "Validate"]),
                    ("Review Before Delivery", ["Local QA", "Claude review", "Repair loop"]),
                    ("Unify Every Channel", ["Telegram", "iMac", "Same pipeline"]),
                    ("Track The Proof", ["Route", "Cost", "Review"]),
                    ("Ship Only When Ready", ["Pass gate", "Attach file", "Record summary"]),
                ],
                "smoke",
                "last_doc",
            )
        finally:
            pptx_visual_assets.generate_gemini_image = old_generate
            _restore_env("GOOGLE_API_KEY", old_google)
            _restore_env("ENABLE_PPTX_GEMINI_IMAGES", old_enabled)
        _require(qa.passed, f"multi-visual PowerPoint flow should pass: {qa.issues}")
        _require(quality_qa.passed, f"document-quality PowerPoint flow should pass: {quality_qa.issues}")
        deck = Presentation(path)
        image_count = sum(1 for slide in deck.slides for shape in slide.shapes if getattr(shape, "shape_type", None) == 13)
        _require(image_count >= len(deck.slides), f"expected at least one inserted image per slide, got {image_count} for {len(deck.slides)} slides")
        quality_deck = Presentation(quality_path)
        quality_image_count = sum(1 for slide in quality_deck.slides for shape in slide.shapes if getattr(shape, "shape_type", None) == 13)
        _require(
            quality_image_count >= len(quality_deck.slides),
            f"expected document-quality deck visuals, got {quality_image_count} for {len(quality_deck.slides)} slides",
        )
        quality_text = " ".join(
            " ".join(getattr(shape, "text", "").split())
            for slide in quality_deck.slides
            for shape in slide.shapes
        )
        _require("FOOD ROUTE" not in quality_text, "document-quality deck should not contain stale FOOD ROUTE label")
        _require("FOOD PLAN" not in quality_text, "document-quality deck should not contain stale FOOD PLAN label")
        _require("QUALITY" in quality_text or "REVIEW" in quality_text, "document-quality deck should use quality-specific labels")
        _require("Focus The Week Around Three Outcomes" not in quality_text, "document-quality deck should not be rebuilt as office-priorities rescue deck")
        _require("Artifact Quality" in quality_text or "Review The Artifact" in quality_text, "document-quality rescue should keep artifact-quality semantics")
        visible_text = " ".join(
            " ".join(getattr(shape, "text", "").split())
            for slide in deck.slides
            for shape in slide.shapes
        )
        _require("SLIDE FOCUS" not in visible_text, "generic SLIDE FOCUS label should not appear")
    print("pptx_multi_visual_flow_smoke: ok")


async def _fake_generate(prompt: str, path: Path) -> Path:
    if "document quality" in prompt.lower() or "kampung ai" in prompt.lower():
        raise RuntimeError("forced image fallback")
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1280, 720), (236, 244, 239)).save(path)
    return path


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
