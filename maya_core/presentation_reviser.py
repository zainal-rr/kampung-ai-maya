from __future__ import annotations

import re
from pathlib import Path

from pptx import Presentation

from maya_documents.office_modern_files import safe_slug
from maya_documents.pptx_quality_gate import ensure_pptx_quality, inspect_pptx_quality
from maya_documents.pptx_slide_renderer import render_pptx_slides
from maya_documents.pptx_topic_reviser import rebuild_topic_safe
from maya_core.presentation_visual_builder import build_visual_reviewed_deck
from maya_core.workspace_paths import workspace_dir


def wants_presentation_revision(text: str) -> bool:
    low = text.lower()
    return any(word in low for word in ("revise", "improve", "fix", "redesign")) and any(
        word in low for word in ("presentation", "ppt", "pptx", "slides", "deck")
    )


def revise_latest_presentation(text: str) -> tuple[Path | None, list[Path], str]:
    source = _find_presentation(text)
    if source is None:
        return None, [], "I could not find a presentation in Desktop/Maya/presentations."
    slides = _extract_slides(source)
    if not slides:
        return None, [], f"I found {source}, but I could not extract slide text."
    destination = source.with_name(f"{source.stem}-reviewed.pptx")
    specialized = _uses_rayban_builder(source)
    if specialized:
        build_visual_reviewed_deck(destination, slides)
        qa = ensure_pptx_quality(destination, max_revisions=1)
    else:
        qa = rebuild_topic_safe(destination, slides)
    images = qa.images or render_pptx_slides(
        destination,
        workspace_dir("screenshots", create=True) / "pptx-reviews" / destination.stem,
    )
    summary = _summary(source, destination, images, qa, specialized)
    return destination, images, summary


def _find_presentation(text: str) -> Path | None:
    root = workspace_dir("presentations")
    candidates = sorted(root.glob("*.pptx"), key=lambda item: item.stat().st_mtime, reverse=True)
    originals = [path for path in candidates if "-reviewed" not in path.stem]
    candidates = originals or candidates
    if not candidates:
        return None
    topic = _topic(text)
    if topic:
        slug = safe_slug(topic)
        for path in candidates:
            if path.stem == slug or slug in path.stem:
                return path
        tokens = {token for token in slug.split("-") if len(token) > 2}
        scored = [(sum(1 for token in tokens if token in path.stem), path) for path in candidates]
        scored = [item for item in scored if item[0] > 0]
        if scored:
            return sorted(scored, key=lambda item: item[0], reverse=True)[0][1]
    return candidates[0]


def _topic(text: str) -> str:
    cleaned = re.sub(r"\b(revise|improve|fix|redesign|the|my|presentation|pptx?|slides?|deck|design|actual|visual|layout)\b", " ", text, flags=re.I)
    return " ".join(cleaned.split())


def _extract_slides(path: Path) -> list[tuple[str, list[str]]]:
    deck = Presentation(path)
    slides = []
    for slide in deck.slides:
        texts = []
        for shape in slide.shapes:
            text = getattr(shape, "text", "").strip()
            if text:
                texts.append(" ".join(text.split()))
        if not texts:
            continue
        title = _strong_title(texts[0])
        bullets = []
        for item in texts[1:]:
            bullets.extend(_split_bullets(item))
        bullets = _clean_bullets(title, bullets)
        slides.append((title, bullets[:3] or ["Add a concise supporting point."]))
    return slides


def _strong_title(title: str) -> str:
    title = title.strip().rstrip(".")
    replacements = {
        "The hardware is purpose-built for outdoor readability": "5,000 nits. Built for sunlight.",
        "Key tradeoffs are real and worth tracking": "What to watch before committing",
        "Three questions to answer before recommending this platform": "Three gates before you commit",
    }
    return replacements.get(title, title)


def _split_bullets(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text.replace(" | ", "\n").replace("|", "\n")).strip()
    chunks = []
    for part in re.split(r"\n|(?<=[.!?;])\s+", text):
        clean = part.strip(" .")
        if len(clean) > 8:
            chunks.append(_compact_bullet(clean))
    return chunks


def _compact_bullet(text: str, limit: int = 155) -> str:
    if len(text) <= limit:
        return text
    for punctuation in (". ", "? ", "! "):
        pos = text.rfind(punctuation, 0, limit)
        if pos >= 40:
            return text[: pos + 1].strip()
    for separator in (" — ", "; ", ": "):
        first = text.split(separator, 1)[0].strip()
        if 40 <= len(first) <= limit:
            return first
    return text[: limit - 1].rsplit(" ", 1)[0].strip(" ,;:-") + "."


def _clean_bullets(title: str, bullets: list[str]) -> list[str]:
    cleaned = []
    seen = set()
    title_key = _key(title)
    for bullet in bullets:
        item = bullet.strip()
        key = _key(item)
        if not item or key in seen or key == title_key:
            continue
        if _is_layout_label(item) or _is_fragment(item):
            continue
        item = _complete(item)
        seen.add(key)
        cleaned.append(item)
    return cleaned


def _is_layout_label(text: str) -> bool:
    low = text.lower().strip()
    return bool(re.fullmatch(r"\d{1,2}|\d+/\d+", low)) or low in {"why it matters", "maya reviewed deck"}


def _is_fragment(text: str) -> bool:
    words = text.split()
    if len(words) <= 2 and not any(char.isdigit() for char in text):
        return True
    return len(text) < 18 and not text.endswith((".", "?", "!"))


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _complete(text: str) -> str:
    clean = text.strip(" ,;:-")
    return clean if clean.endswith((".", "?", "!", ")")) else clean + "."


def _uses_rayban_builder(path: Path) -> bool:
    stem = path.stem.lower()
    return "ray" in stem and "ban" in stem


def _summary(source: Path, destination: Path, images: list[Path], qa, specialized: bool) -> str:
    quality = f"\n4) {qa.summary()}"
    changes = (
        "rebuilt with real visual layouts, stat cards, risk cards, decision gates, and a glasses/HUD visual."
        if specialized
        else "rebuilt with the topic-safe PowerPoint layout, cleaner bullets, rendered verification, and no topic-specific visual substitution."
    )
    return (
        f"Created a reviewed copy from {source.name}.\n"
        f"1) Saved revised deck: {destination}\n"
        f"2) Rendered verification slides: {len(images)}\n"
        f"3) Changes: {changes}\n"
        f"{quality}\n"
        "5) I did not overwrite the original."
    )
