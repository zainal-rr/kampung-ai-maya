from __future__ import annotations

import os
import textwrap
import time
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from pptx import Presentation


EMU_PER_INCH = 914400
PX_PER_INCH = 144


class PptxRenderTimeout(TimeoutError):
    """Raised when slide rendering exceeds its time budget. The quality gate
    treats this as a non-blocking note (a slow renderer says nothing about
    the deck), unlike real render failures which stay blockers.
    Live incident 2026-06-11: render QA held a correct deck for 453s and then
    delivered it as not-final."""


def _render_deadline_seconds() -> float:
    try:
        return float(os.getenv("MAYA_PPTX_RENDER_TIMEOUT_SECONDS", "90"))
    except ValueError:
        return 90.0


def render_pptx_slides(
    path: Path,
    output_dir: Path,
    limit: int = 8,
    deadline_seconds: float | None = None,
) -> list[Path]:
    if deadline_seconds is None:
        deadline_seconds = _render_deadline_seconds()
    started = time.monotonic()
    output_dir.mkdir(parents=True, exist_ok=True)
    deck = Presentation(path)
    width = _emu_to_px(deck.slide_width)
    height = _emu_to_px(deck.slide_height)
    files = []
    for index, slide in enumerate(deck.slides, 1):
        if index > limit:
            break
        if deadline_seconds > 0 and (time.monotonic() - started) > deadline_seconds:
            raise PptxRenderTimeout(
                f"slide rendering exceeded {deadline_seconds:.0f}s at slide {index} of {len(deck.slides)}"
            )
        image = Image.new("RGB", (width, height), _background_rgb(slide))
        draw = ImageDraw.Draw(image)
        for shape in slide.shapes:
            _draw_shape(image, draw, shape)
        out = output_dir / f"{path.stem}-slide-{index:02d}.jpg"
        image.save(out, "JPEG", quality=92)
        files.append(out)
    return files


def _draw_shape(canvas: Image.Image, draw: ImageDraw.ImageDraw, shape) -> None:
    x, y, w, h = [_emu_to_px(value) for value in (shape.left, shape.top, shape.width, shape.height)]
    if getattr(shape, "shape_type", None) == 13:
        _draw_picture(canvas, draw, shape, x, y, w, h)
        return
    fill = _fill_rgb(shape)
    line = _line_rgb(shape)
    if fill:
        draw.rounded_rectangle((x, y, x + w, y + h), radius=10, fill=fill, outline=line)
    elif line:
        draw.rectangle((x, y, x + w, y + h), outline=line)
    text = getattr(shape, "text", "").strip()
    if text:
        _draw_text(draw, text, x + 12, y + 10, max(w - 24, 80), h, _text_rgb(shape))
def _draw_picture(canvas: Image.Image, draw: ImageDraw.ImageDraw, shape, x: int, y: int, w: int, h: int) -> None:
    try:
        with Image.open(BytesIO(shape.image.blob)) as image:
            image = image.convert("RGB")
            cropped = _crop_picture(image, shape)
            fitted = ImageOps.fit(cropped, (max(w, 1), max(h, 1)), method=Image.Resampling.LANCZOS)
            canvas.paste(fitted, (x, y))
            fitted.close()
            if cropped is not image:
                cropped.close()
    except Exception:
        draw.rectangle((x, y, x + w, y + h), outline=(110, 130, 120), width=2)
        draw.line((x, y, x + w, y + h), fill=(110, 130, 120), width=2)
        draw.line((x + w, y, x, y + h), fill=(110, 130, 120), width=2)


def _crop_picture(image: Image.Image, shape) -> Image.Image:
    left = _crop_fraction(getattr(shape, "crop_left", 0))
    right = _crop_fraction(getattr(shape, "crop_right", 0))
    top = _crop_fraction(getattr(shape, "crop_top", 0))
    bottom = _crop_fraction(getattr(shape, "crop_bottom", 0))
    if not any((left, right, top, bottom)):
        return image
    width, height = image.size
    x1 = int(width * left)
    x2 = int(width * (1 - right))
    y1 = int(height * top)
    y2 = int(height * (1 - bottom))
    if x2 <= x1 or y2 <= y1:
        return image
    return image.crop((x1, y1, x2, y2))


def _crop_fraction(value) -> float:
    try:
        return max(0.0, min(0.49, float(value or 0)))
    except Exception:
        return 0.0


def _draw_text(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, width: int, height: int, color: tuple[int, int, int]) -> None:
    font = _font(_font_size(text, height))
    line_height = int(font.size * 1.28)
    max_chars = max(int(width / max(font.size * 0.55, 8)), 12)
    lines = []
    for paragraph in text.splitlines() or [text]:
        lines.extend(textwrap.wrap(paragraph, width=max_chars) or [""])
    for idx, line in enumerate(lines):
        top = y + idx * line_height
        if top + line_height > y + height:
            draw.text((x, top), "...", fill=color, font=font)
            break
        draw.text((x, top), line, fill=color, font=font)


def _font(size: int):
    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _font_size(text: str, height: int) -> int:
    if len(text) < 70 and height > 120:
        return 28
    if len(text) < 150:
        return 22
    return 18


def _background_rgb(slide) -> tuple[int, int, int]:
    try:
        color = slide.background.fill.fore_color.rgb
        return _rgb_tuple(color)
    except Exception:
        return (248, 250, 247)


def _fill_rgb(shape) -> tuple[int, int, int] | None:
    try:
        fill = shape.fill
        if not fill or fill.type is None:
            return None
        return _rgb_tuple(fill.fore_color.rgb)
    except Exception:
        return None


def _line_rgb(shape) -> tuple[int, int, int] | None:
    try:
        return _rgb_tuple(shape.line.color.rgb)
    except Exception:
        return None


def _text_rgb(shape) -> tuple[int, int, int]:
    try:
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                rgb = run.font.color.rgb
                if rgb:
                    return _rgb_tuple(rgb)
    except Exception:
        pass
    return (31, 48, 41)


def _rgb_tuple(color) -> tuple[int, int, int]:
    return tuple(int(str(color)[idx:idx + 2], 16) for idx in (0, 2, 4))


def _emu_to_px(value) -> int:
    return int(int(value) / EMU_PER_INCH * PX_PER_INCH)
