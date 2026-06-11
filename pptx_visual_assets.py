from __future__ import annotations

import asyncio
import math
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw
from pptx import Presentation
from pptx.util import Inches

from gemini_image import generate_gemini_image
from office_files import safe_slug
from workspace_paths import workspace_dir


VISUAL_TOPIC_MARKERS = (
    "food", "trip", "travel", "restaurant", "itinerary", "product", "pitch",
    "venue", "place", "city", "architecture", "concept", "diagram", "visual",
    "brand", "marketing", "tourism", "hotel", "cafe", "ai", "agent",
    "workflow", "system", "quality", "document", "artifact", "process",
    "technical", "strategy", "roadmap",
)
PLAIN_TOPIC_MARKERS = (
    "plain", "internal notes", "text only", "text-only", "notes only",
    "no images", "no visuals", "without images", "minimal deck",
)


def topic_benefits_from_visuals(topic: str) -> bool:
    import re as _re

    lowered = " ".join(str(topic).lower().split())
    # Explicitly plain/internal decks never auto-request generated images.
    if any(marker in lowered for marker in PLAIN_TOPIC_MARKERS):
        return False
    # Word-boundary matching: bare substrings were too loose ("ai" matched
    # "plain", "trip" matched "stripped").
    return any(_re.search(rf"\b{_re.escape(marker)}\b", lowered) for marker in VISUAL_TOPIC_MARKERS)


async def add_gemini_visual_asset(path: Path, topic: str, max_images: int | None = None) -> tuple[bool, str]:
    if os.getenv("ENABLE_PPTX_GEMINI_IMAGES", "1") == "0":
        return False, "Gemini PPTX images disabled."
    if not topic_benefits_from_visuals(topic):
        return False, "Topic does not need generated visuals."
    if not os.getenv("GOOGLE_API_KEY"):
        return False, "Gemini image generation unavailable: GOOGLE_API_KEY not configured."
    prompts = _image_prompts(path, topic, max_images=max_images)
    image_paths: list[Path] = []
    fallback_used = False
    timeout_s = _image_timeout_seconds()
    try:
        for index, prompt in enumerate(prompts, 1):
            image_path = _image_scratch_dir() / f"{safe_slug(topic, 56)}-{index}.png"
            if fallback_used:
                await asyncio.to_thread(_fallback_visual, image_path, topic, index)
            else:
                try:
                    await asyncio.wait_for(generate_gemini_image(prompt, image_path), timeout=timeout_s)
                except Exception:
                    fallback_used = True
                    await asyncio.to_thread(_fallback_visual, image_path, topic, index)
            image_paths.append(image_path)
    except Exception as exc:
        return False, f"Gemini image generation failed: {exc}"
    inserted, note = await asyncio.to_thread(_insert_visuals, path, image_paths)
    if inserted and fallback_used:
        note = f"{note} Gemini image generation timed out or failed; inserted local abstract fallback visuals."
    return inserted, note


def _image_scratch_dir() -> Path:
    """Scratch directory for generated images BEFORE they are embedded.

    Live incident 2026-06-11 (drone deck, 313.9s): writes to
    Desktop/Maya/artifacts/pptx-images stalled with `[Errno 60] Operation
    timed out` because Desktop is iCloud-synced. The png files here are
    intermediate — they get embedded into the .pptx — so the scratch belongs
    on a guaranteed-local path. Override: MAYA_PPTX_IMAGE_SCRATCH_DIR."""
    override = os.getenv("MAYA_PPTX_IMAGE_SCRATCH_DIR", "").strip()
    base = Path(override).expanduser() if override else Path(tempfile.gettempdir()) / "maya-pptx-images"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _image_timeout_seconds() -> float:
    try:
        return max(5.0, min(90.0, float(os.getenv("PPTX_GEMINI_IMAGE_TIMEOUT", "12"))))
    except ValueError:
        return 25.0


def _fallback_visual(path: Path, topic: str, index: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    width, height = 1280, 720
    image = Image.new("RGB", (width, height), (13, 18, 27))
    draw = ImageDraw.Draw(image)
    palette = [(54, 73, 92), (211, 161, 74), (74, 111, 97), (30, 38, 55), (232, 238, 230)]
    for y in range(0, height, 18):
        shade = min(255, 18 + y // 12)
        draw.rectangle([0, y, width, y + 18], fill=(13, min(35, shade), min(50, shade + 8)))
    for step in range(9):
        x = 90 + step * 130
        y = 110 + ((step * 53 + index * 47) % 330)
        color = palette[(step + index) % len(palette)]
        draw.rounded_rectangle([x, y, x + 210, y + 96], radius=18, fill=color, outline=(232, 238, 230), width=2)
    for step in range(7):
        x1 = 150 + step * 145
        y1 = 520 - ((step * 41 + index * 29) % 180)
        x2 = min(width - 120, x1 + 160)
        y2 = max(80, y1 - 95)
        draw.line([x1, y1, x2, y2], fill=(211, 161, 74), width=6)
        draw.ellipse([x2 - 10, y2 - 10, x2 + 10, y2 + 10], fill=(211, 161, 74))
    draw.rectangle([70, 590, 760, 604], fill=(211, 161, 74))
    draw.rectangle([70, 620, 520, 630], fill=(232, 238, 230))
    image.save(path)
    return path


def _image_prompts(path: Path, topic: str, max_images: int | None = None) -> list[str]:
    deck = Presentation(path)
    slides = list(deck.slides)
    max_images = max_images or visual_image_target(len(slides))
    prompts = []
    for index in range(max_images):
        slide = slides[index % len(slides)]
        texts = [" ".join(getattr(shape, "text", "").split()) for shape in slide.shapes]
        slide_topic = " / ".join(text for text in texts[:4] if text) or topic
        prompts.append(_image_prompt(topic, slide_topic, index))
    return prompts


def _image_prompt(topic: str, slide_topic: str, index: int) -> str:
    lowered = str(topic).lower()
    if any(word in lowered for word in ("food", "restaurant", "cafe", "trip", "travel", "tourism")):
        if any(marker in lowered for marker in ("pastel", "light theme", "light mode", "bright theme", "not dark", "no dark")):
            style = (
                "Use bright high-key editorial travel and food photography with natural light, "
                "appetizing real food texture, and a clean magazine feel."
            )
        else:
            style = (
                "Use premium editorial travel and food photography with controlled contrast, "
                "rich shadows, appetizing real food texture, and a dark-theme presentation fit. "
                "Avoid flat black studio emptiness; keep the food and place visually inspectable."
            )
    elif any(word in lowered for word in ("cyber", "security", "architecture", "risk", "incident", "command")):
        style = "Use dark premium technical editorial imagery with high contrast and controlled light."
    elif any(word in lowered for word in ("ai", "agent", "workflow", "system", "quality", "document", "artifact", "process", "strategy", "roadmap")):
        style = (
            "Use premium abstract product-system editorial imagery: layered documents, "
            "workflow paths, review checkpoints, subtle interface surfaces, controlled dark lighting, "
            "and high-end technology composition."
        )
    else:
        style = "Use polished editorial imagery with a clear subject and strong composition."
    return (
        "Create a clean, presentation-ready 16:9 visual for a PowerPoint deck. "
        "No text, labels, logos, watermarks, UI chrome, or captions inside the image. "
        f"{style} "
        f"Deck topic: {topic}. Slide focus: {slide_topic}. Visual number: {index + 1}."
    )


def _insert_visuals(path: Path, image_paths: list[Path]) -> tuple[bool, str]:
    deck = Presentation(path)
    if not deck.slides:
        return False, "Deck has no slides for image insertion."
    inserted = 0
    for index, image_path in enumerate(image_paths):
        slide_index = _target_slide_index(index, len(deck.slides))
        if slide_index is None:
            break
        x, y, width, height = _picture_slot(index, slide_index, extra=index >= len(deck.slides))
        _add_picture_cover(deck.slides[slide_index], image_path, x, y, width, height)
        inserted += 1
    deck.save(path)
    if not inserted:
        return False, "No visual slots were available for image insertion."
    return True, f"Inserted {inserted} Gemini visual assets."


def visual_image_cap(slide_count: int) -> int:
    if slide_count <= 0:
        return 0
    return max(1, math.ceil(slide_count * 1.3))


def visual_image_target(slide_count: int) -> int:
    if slide_count <= 0:
        return 0
    cap = visual_image_cap(slide_count)
    try:
        configured = int(os.getenv("PPTX_GEMINI_IMAGE_MAX", str(slide_count)))
    except ValueError:
        configured = slide_count
    return max(1, min(configured, cap))


def required_visual_image_count(slide_count: int) -> int:
    if slide_count <= 0:
        return 0
    return min(slide_count, visual_image_target(slide_count))


def _target_slide_index(image_index: int, slide_count: int) -> int | None:
    if slide_count <= 0:
        return None
    if image_index < slide_count:
        return image_index
    if slide_count == 1:
        return 0
    return 1 + ((image_index - slide_count) % (slide_count - 1))


def _picture_slot(image_index: int, slide_index: int, extra: bool = False) -> tuple[float, float, float, float]:
    if extra:
        if slide_index == 0:
            return 10.15, 5.18, 1.65, 1.05
        if slide_index % 3 == 0:
            return 10.62, 2.82, 1.52, 0.92
        image_left = slide_index % 2 == 1
        return (10.28, 5.08, 1.55, 1.0) if image_left else (4.75, 5.08, 1.55, 1.0)
    if slide_index == 0:
        return 7.25, 1.0, 5.1, 3.55
    if slide_index % 3 == 0:
        return 0.86, 1.34, 11.65, 2.62
    image_left = slide_index % 2 == 1
    return (0.86, 1.44, 5.73, 4.83) if image_left else (6.56, 1.44, 5.73, 4.83)


def _add_picture_cover(slide, image_path: Path, x: float, y: float, width: float, height: float):
    picture = slide.shapes.add_picture(
        str(image_path),
        Inches(x),
        Inches(y),
        width=Inches(width),
        height=Inches(height),
    )
    _apply_center_crop(picture, image_path, width / height)
    return picture


def _apply_center_crop(picture, image_path: Path, frame_ratio: float) -> None:
    with Image.open(image_path) as image:
        image_width, image_height = image.size
    if image_width <= 0 or image_height <= 0 or frame_ratio <= 0:
        return
    image_ratio = image_width / image_height
    if abs(image_ratio - frame_ratio) < 0.01:
        return
    if frame_ratio > image_ratio:
        crop_total = 1 - (image_ratio / frame_ratio)
        crop = max(0, min(0.49, crop_total / 2))
        picture.crop_top = crop
        picture.crop_bottom = crop
    else:
        crop_total = 1 - (frame_ratio / image_ratio)
        crop = max(0, min(0.49, crop_total / 2))
        picture.crop_left = crop
        picture.crop_right = crop
