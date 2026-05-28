from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pptx import Presentation

from presentation_visual_builder import build_visual_reviewed_deck
from pptx_slide_renderer import render_pptx_slides
from workspace_paths import workspace_dir


BAD_PHRASES = (
    "visual anchor",
    "add a concise supporting point",
    "key concept",
    "supporting detail",
    "prepared by maya",
)
BAD_ENDINGS = ("launched in", "with", "and", "the", "to")


@dataclass
class PptxQualityResult:
    passed: bool
    issues: list[str]
    images: list[Path]
    revisions: int = 0
    polish: str = ""

    def summary(self) -> str:
        if self.passed:
            return f"Visual QA passed. {self.polish}".strip()
        shown = "; ".join(self.issues[:4])
        return f"Visual QA still has issues: {shown}."


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
    try:
        images = render_pptx_slides(path, _review_dir(path), limit=80)
    except Exception as exc:
        issues.append(f"render failed: {exc}")
    if len(images) != len(deck.slides):
        issues.append("rendered slide count does not match deck slide count")
    return PptxQualityResult(not issues, issues, images)


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
    if "..." in joined:
        issues.append(f"slide {index} contains ellipsis overflow")
    for text in texts:
        if _looks_truncated(text):
            issues.append(f"slide {index} has truncated text")
            break
    return issues


def _looks_truncated(text: str) -> bool:
    low = text.lower().rstrip(" .")
    if len(text) > 70 and not text.rstrip().endswith((".", "?", "!", ")")):
        return True
    return any(low.endswith(ending) for ending in BAD_ENDINGS)


def _clean(text: str) -> str:
    return " ".join((text or "").split())


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
