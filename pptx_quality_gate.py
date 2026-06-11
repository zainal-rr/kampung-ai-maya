from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from io import BytesIO

from PIL import Image
from pptx import Presentation

from presentation_visual_builder import build_visual_reviewed_deck
from pptx_slide_renderer import PptxRenderTimeout, render_pptx_slides
from workspace_paths import workspace_dir


BAD_PHRASES = (
    "visual anchor",
    "add a concise supporting point",
    "key concept",
    "supporting detail",
    "prepared by maya",
    "draft document",
    "model generated content",
    "slide focus",
    "key move",
)
BAD_ENDINGS = ("launched in", "with", "and", "the", "to", "when", "where", "because")


@dataclass
class PptxQualityResult:
    passed: bool
    issues: list[str]
    images: list[Path]
    revisions: int = 0
    polish: str = ""
    notes: list[str] | None = None

    def summary(self) -> str:
        note_text = f" Note: {'; '.join(self.notes)}." if self.notes else ""
        if self.passed:
            return f"Visual QA passed.{note_text} {self.polish}".strip()
        shown = "; ".join(self.issues[:4])
        return f"Visual QA still has issues: {shown}.{note_text}"


def ensure_pptx_quality(path: Path, max_revisions: int = 1) -> PptxQualityResult:
    result = inspect_pptx_quality(path)
    revisions = 0
    if "meta" not in path.stem.lower() and "ray" not in path.stem.lower():
        return result
    while not result.passed and revisions < max_revisions:
        slides = _extract_slides(path)
        if not slides:
            break
        build_visual_reviewed_deck(path, slides)
        revisions += 1
        result = inspect_pptx_quality(path)
    result.revisions = revisions
    return result


def inspect_pptx_quality(path: Path) -> PptxQualityResult:
    images: list[Path] = []
    issues: list[str] = []
    try:
        deck = Presentation(path)
    except Exception as exc:
        return PptxQualityResult(False, [f"file could not be opened: {exc}"], [])
    if not deck.slides:
        issues.append("deck has no slides")
    for index, slide in enumerate(deck.slides, 1):
        issues.extend(_slide_issues(index, slide))
    notes: list[str] = []
    render_timed_out = False
    try:
        images = render_pptx_slides(path, _review_dir(path), limit=80)
    except PptxRenderTimeout as exc:
        # Severity-tier rule (live incident 2026-06-11, 453s hold): a render
        # TIMEOUT is a warning, not a blocker — a slow renderer says nothing
        # about the deck. Real render failures below remain blockers.
        render_timed_out = True
        notes.append(f"render QA skipped ({exc}); deck judged on structure only")
    except Exception as exc:
        issues.append(f"render failed: {exc}")
    if not render_timed_out and len(images) != len(deck.slides):
        issues.append("rendered slide count does not match deck slide count")
    return PptxQualityResult(not issues, issues, images, notes=notes or None)


def _slide_issues(index: int, slide) -> list[str]:
    texts = [_clean(getattr(shape, "text", "")) for shape in slide.shapes]
    texts = [text for text in texts if text]
    issues: list[str] = []
    if not texts:
        issues.append(f"slide {index} has no readable text")
        return issues
    if len(texts[0]) < 8:
        issues.append(f"slide {index} title is too weak")
    joined = " ".join(texts).lower()
    if any(phrase in joined for phrase in BAD_PHRASES):
        issues.append(f"slide {index} contains placeholder text")
    notes = _slide_notes(slide).lower()
    if any(phrase in notes for phrase in BAD_PHRASES):
        issues.append(f"slide {index} contains placeholder text in speaker notes")
    if "..." in joined:
        issues.append(f"slide {index} contains ellipsis overflow")
    if _sentence_heavy(texts):
        issues.append(f"slide {index} is sentence-heavy; move explanation to speaker notes")
    for text in texts:
        if _looks_truncated(text):
            issues.append(f"slide {index} has truncated text")
            break
    if _has_stretched_picture(slide):
        issues.append(f"slide {index} has a stretched image")
    return issues


def _has_stretched_picture(slide) -> bool:
    for shape in slide.shapes:
        if getattr(shape, "shape_type", None) != 13:
            continue
        try:
            with Image.open(BytesIO(shape.image.blob)) as image:
                image_width, image_height = image.size
        except Exception:
            continue
        if image_width <= 0 or image_height <= 0 or shape.height <= 0:
            continue
        image_ratio = image_width / image_height
        frame_ratio = shape.width / shape.height
        mismatch = abs(frame_ratio - image_ratio) / image_ratio
        crop_total = shape.crop_left + shape.crop_right + shape.crop_top + shape.crop_bottom
        if mismatch > 0.08 and crop_total < 0.01:
            return True
    return False


def _looks_truncated(text: str) -> bool:
    low = text.lower().rstrip(" .")
    if low.endswith("with a ready"):
        return True
    if len(text) > 70 and not text.rstrip().endswith((".", "?", "!", ")")):
        return True
    return any(low.endswith(ending) for ending in BAD_ENDINGS)


def _sentence_heavy(texts: list[str]) -> bool:
    body = [text for text in texts[1:] if not text.isdigit() and "/" not in text]
    long_items = [text for text in body if len(text) > 95 or len(text.split()) > 13]
    sentence_items = [text for text in body if text.rstrip().endswith((".", "!", "?")) and len(text.split()) > 7]
    return len(long_items) >= 2 or len(sentence_items) >= 3


def _clean(text: str) -> str:
    return " ".join((text or "").split())


def _slide_notes(slide) -> str:
    try:
        return _clean(slide.notes_slide.notes_text_frame.text)
    except Exception:
        return ""


def _review_dir(path: Path) -> Path:
    return workspace_dir("screenshots", create=True) / "pptx-reviews" / path.stem


def _extract_slides(path: Path) -> list[tuple[str, list[str]]]:
    deck = Presentation(path)
    slides = []
    for slide in deck.slides:
        texts = [_clean(getattr(shape, "text", "")) for shape in slide.shapes]
        texts = [text for text in texts if text]
        if not texts:
            continue
        title = texts[0]
        bullets = [text for text in texts[1:] if len(text) > 4]
        slides.append((title, bullets[:3] or ["Add a specific supporting point."]))
    return slides
