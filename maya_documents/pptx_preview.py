from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from maya_documents.office_files import safe_slug
from maya_documents.pptx_slide_renderer import render_pptx_slides


def powerpoint_contact_sheet(path: Path, *, max_slides: int = 8) -> Path | None:
    preview_root = _preview_root(path)
    slides = render_pptx_slides(path, preview_root / "slides", limit=max_slides)
    if not slides:
        return None
    images = [Image.open(slide).convert("RGB") for slide in slides]
    try:
        return _contact_sheet(path, images, preview_root)
    finally:
        for image in images:
            image.close()


def _contact_sheet(path: Path, images: list[Image.Image], preview_root: Path) -> Path:
    preview_root.mkdir(parents=True, exist_ok=True)
    thumb_w = 480
    thumb_h = int(thumb_w * 9 / 16)
    padding = 26
    label_h = 30
    cols = 2 if len(images) <= 4 else 3
    rows = (len(images) + cols - 1) // cols
    width = cols * thumb_w + (cols + 1) * padding
    height = rows * (thumb_h + label_h) + (rows + 1) * padding
    sheet = Image.new("RGB", (width, height), (248, 247, 242))
    draw = ImageDraw.Draw(sheet)
    for index, image in enumerate(images):
        row = index // cols
        col = index % cols
        x = padding + col * (thumb_w + padding)
        y = padding + row * (thumb_h + label_h + padding)
        thumb = image.copy()
        thumb.thumbnail((thumb_w, thumb_h))
        sheet.paste(thumb, (x, y))
        draw.rectangle((x, y, x + thumb.width - 1, y + thumb.height - 1), outline=(128, 142, 132), width=2)
        draw.text((x, y + thumb_h + 8), f"Slide {index + 1}", fill=(23, 35, 31))
        thumb.close()
    out = preview_root / f"{safe_slug(path.stem, 72)}-preview.jpg"
    sheet.save(out, "JPEG", quality=92)
    return out


def _preview_root(path: Path) -> Path:
    """Local scratch for preview renders.

    Desktop/Maya can be iCloud-synced on Zainal's iMac. Live tests repeatedly
    hit `[Errno 60] Operation timed out` while writing preview JPEGs there.
    Preview/contact-sheet images are scratch artifacts, so default to local tmp.
    Override with MAYA_PPTX_PREVIEW_DIR if a durable preview directory is needed.
    """
    override = os.getenv("MAYA_PPTX_PREVIEW_DIR", "").strip()
    base = Path(override).expanduser() if override else Path(tempfile.gettempdir()) / "maya-pptx-previews"
    return base / path.stem
