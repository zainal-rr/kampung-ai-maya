from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from PIL import Image
from pptx import Presentation

import pptx_visual_assets
from pptx_document_flow import create_powerpoint_with_qa
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
        finally:
            pptx_visual_assets.generate_gemini_image = old_generate
            _restore_env("GOOGLE_API_KEY", old_google)
            _restore_env("ENABLE_PPTX_GEMINI_IMAGES", old_enabled)
        _require(qa.passed, f"multi-visual PowerPoint flow should pass: {qa.issues}")
        deck = Presentation(path)
        image_count = sum(1 for slide in deck.slides for shape in slide.shapes if getattr(shape, "shape_type", None) == 13)
        _require(image_count >= len(deck.slides), f"expected at least one inserted image per slide, got {image_count} for {len(deck.slides)} slides")
        visible_text = " ".join(
            " ".join(getattr(shape, "text", "").split())
            for slide in deck.slides
            for shape in slide.shapes
        )
        _require("SLIDE FOCUS" not in visible_text, "generic SLIDE FOCUS label should not appear")
    print("pptx_multi_visual_flow_smoke: ok")


async def _fake_generate(prompt: str, path: Path) -> Path:
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
