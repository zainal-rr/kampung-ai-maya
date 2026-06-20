from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from docx import Document

from maya_core.execution_broker import CommandSpec, run_command


@dataclass(frozen=True)
class WordVisualQuality:
    issues: list[str]
    warnings: list[str]
    preview_status: str = ""


def inspect_word_visual_quality(path: Path) -> WordVisualQuality:
    issues: list[str] = []
    warnings: list[str] = []
    try:
        doc = Document(path)
    except Exception as exc:
        return WordVisualQuality([f"Word visual QA could not open file: {exc}"], warnings)
    issues.extend(_page_setup_issues(doc))
    issues.extend(_paragraph_layout_issues(doc))
    preview_status = _optional_html_preview(path, warnings)
    return WordVisualQuality(issues, warnings, preview_status)


def _page_setup_issues(doc: Document) -> list[str]:
    issues: list[str] = []
    for index, section in enumerate(doc.sections, start=1):
        margins = (
            section.top_margin.inches,
            section.bottom_margin.inches,
            section.left_margin.inches,
            section.right_margin.inches,
        )
        if any(value < 0.35 or value > 1.5 for value in margins):
            issues.append(f"section {index} has unusual margins")
    return issues


def _paragraph_layout_issues(doc: Document) -> list[str]:
    issues: list[str] = []
    paragraphs = [p for p in doc.paragraphs if p.text.strip()]
    if not paragraphs:
        return ["document has no visible paragraphs"]
    first_style = _style_name(paragraphs[0]).lower()
    if "title" not in first_style and "heading" not in first_style:
        issues.append("first visible paragraph is not styled as a title or heading")
    heading_seen = False
    repeated_headings: set[str] = set()
    seen_headings: set[str] = set()
    body_runs_without_heading = 0
    for paragraph in paragraphs:
        text = " ".join(paragraph.text.split())
        style = _style_name(paragraph).lower()
        is_heading = "heading" in style or "title" in style
        if is_heading:
            key = text.casefold()
            if key in seen_headings:
                repeated_headings.add(text)
            seen_headings.add(key)
            heading_seen = True
            body_runs_without_heading = 0
            if len(text.split()) > 16:
                issues.append(f"heading is too long for readable Word layout: {text[:80]}")
            continue
        if not heading_seen:
            body_runs_without_heading += 1
        if _paragraph_word_count(text) > 95 and not _monospace_paragraph(paragraph):
            issues.append(f"paragraph is too long for readable Word layout: {text[:80]}")
        if len(text) > 650 and not _monospace_paragraph(paragraph):
            issues.append(f"paragraph line is visually dense: {text[:80]}")
    if body_runs_without_heading >= 2:
        issues.append("body text appears before the first useful heading")
    for heading in sorted(repeated_headings)[:3]:
        issues.append(f"repeated heading weakens document layout: {heading}")
    return issues


def _optional_html_preview(path: Path, warnings: list[str]) -> str:
    textutil = shutil.which("textutil")
    if not textutil:
        warnings.append("Word HTML preview skipped: textutil unavailable")
        return ""
    with tempfile.TemporaryDirectory(prefix="maya-word-preview-") as tmp:
        preview = Path(tmp) / (path.stem + ".html")
        proc = run_command(CommandSpec(
            argv=(textutil, "-convert", "html", "-output", str(preview), str(path)),
            cwd=path.parent,
            profile="workspace_write",
            text=True,
            timeout=12,
            check=False,
            write_roots=(Path(tmp),),
        )).to_completed_process()
        if proc.returncode != 0 or not preview.exists():
            warnings.append("Word HTML preview skipped: textutil conversion failed")
            return ""
        if preview.stat().st_size < 800:
            warnings.append("Word HTML preview looked unusually small")
        return "textutil html preview generated"


def _style_name(paragraph) -> str:
    return str(getattr(getattr(paragraph, "style", None), "name", "") or "")


def _paragraph_word_count(text: str) -> int:
    return len([word for word in text.split() if word.strip()])


def _monospace_paragraph(paragraph) -> bool:
    for run in paragraph.runs:
        font_name = getattr(run.font, "name", "") or ""
        if "courier" in font_name.lower() or "mono" in font_name.lower():
            return True
    return False
