from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from cost_tracker import record_usage
from models import TheSteward
from provider_capabilities import CAPABILITIES


SKILL_IDS = {
    "docx": "word_artifact_quality",
    "xlsx": "excel_artifact_quality",
    "pptx": "powerpoint_artifact_quality",
    "html": "html_app_artifact_quality",
}


@dataclass
class ArtifactQualityResult:
    artifact_type: str
    path: str = ""
    passed: bool = True
    summary: str = ""
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    draft_model: str = ""
    review_model: str = ""
    validation_steps: list[str] = field(default_factory=list)
    repair_attempted: bool = False
    delivery_ready: bool = True

    def merge(self, other: "ArtifactQualityResult") -> "ArtifactQualityResult":
        return ArtifactQualityResult(
            artifact_type=self.artifact_type,
            path=self.path or other.path,
            passed=self.passed and other.passed,
            summary=other.summary or self.summary,
            issues=[*self.issues, *other.issues],
            warnings=[*self.warnings, *other.warnings],
            draft_model=self.draft_model or other.draft_model,
            review_model=other.review_model or self.review_model,
            validation_steps=[*self.validation_steps, *other.validation_steps],
            repair_attempted=self.repair_attempted or other.repair_attempted,
            delivery_ready=self.delivery_ready and other.delivery_ready,
        )

    def short_issue_text(self) -> str:
        return "; ".join(self.issues[:4]) or self.summary or "quality review did not pass"


def artifact_skill_context(artifact_type: str) -> str:
    skill_id = SKILL_IDS.get(artifact_type.lower(), "")
    if not skill_id:
        return ""
    for folder in ("active", "proposed"):
        path = Path("maya_skills") / folder / f"{skill_id}.md"
        if path.exists():
            return path.read_text("utf-8")[:12000]
    return ""


def validate_html_content(topic: str, html: str) -> ArtifactQualityResult:
    lowered = html.lower()
    issues: list[str] = []
    required = ("<!doctype", "<html", "<head", "<body", "<style", "<script")
    for marker in required:
        if marker not in lowered:
            issues.append(f"missing {marker}")
    if not any(marker in lowered for marker in ("<button", "<input", "<select", "<textarea", "addeventlistener", "localstorage")):
        issues.append("no real interactive controls")
    bad_markers = ("<.doctype", "charset=\"utf 8\"", "width=device width", "initial scale")
    issues.extend(f"malformed HTML marker: {marker}" for marker in bad_markers if marker in lowered)
    if "```" in html:
        issues.append("markdown code fence leaked into HTML file")
    if re.search(r"\b(?:font|box|border|text|grid|max|min|list|justify|align|flex|margin|padding)\s+(?:family|sizing|radius|align|columns|width|style|content|items|wrap|bottom|top|left|right)\s*:", html):
        issues.append("CSS contains broken property names with spaces")
    summary = f"HTML app QA for {topic}: valid single-file app structure."
    return ArtifactQualityResult(
        "html",
        passed=not issues,
        summary=summary,
        issues=issues,
        validation_steps=["html structure", "interactive controls", "common syntax corruption"],
        delivery_ready=not issues,
    )


def validate_docx_path(path: Path) -> ArtifactQualityResult:
    from docx import Document

    issues: list[str] = []
    paragraphs: list[str] = []
    headings: list[str] = []
    try:
        doc = Document(path)
    except Exception as exc:
        return ArtifactQualityResult("docx", str(path), False, issues=[f"Word file could not be opened: {exc}"], delivery_ready=False)
    for paragraph in doc.paragraphs:
        text = " ".join(paragraph.text.split())
        if not text:
            continue
        paragraphs.append(text)
        style_name = getattr(getattr(paragraph, "style", None), "name", "")
        if "heading" in style_name.lower():
            headings.append(text)
    word_count = sum(len(item.split()) for item in paragraphs)
    joined = "\n".join(paragraphs).lower()
    if word_count < 40:
        issues.append("document has too little real content")
    if not headings:
        issues.append("document has no useful headings")
    bad = ("lorem ipsum", "todo", "placeholder", "draft document about", "add a specific point", "```", "###")
    issues.extend(f"placeholder or malformed text found: {marker}" for marker in bad if marker in joined)
    summary = _summary_from_text(paragraphs, "Word document")
    return ArtifactQualityResult(
        "docx",
        str(path),
        not issues,
        summary,
        issues,
        validation_steps=["docx open", "headings", "content density", "placeholder scan"],
        delivery_ready=not issues,
    )


def validate_xlsx_path(path: Path, topic: str = "") -> ArtifactQualityResult:
    from openpyxl import load_workbook

    issues: list[str] = []
    try:
        book = load_workbook(path, data_only=False)
    except Exception as exc:
        return ArtifactQualityResult("xlsx", str(path), False, issues=[f"Excel file could not be opened: {exc}"], delivery_ready=False)
    if not book.sheetnames:
        issues.append("workbook has no sheets")
    non_empty = 0
    formulas = 0
    headers = 0
    for sheet in book.worksheets:
        if sheet.max_row < 3 or sheet.max_column < 2:
            issues.append(f"{sheet.title} has too little structure")
        if not sheet.freeze_panes:
            issues.append(f"{sheet.title} has no frozen header/reference pane")
        for row in sheet.iter_rows(values_only=True):
            values = [value for value in row if value not in (None, "")]
            if values:
                non_empty += len(values)
                if len(values) >= 3:
                    headers += 1
            formulas += sum(1 for value in values if isinstance(value, str) and value.startswith("="))
    if non_empty < 8:
        issues.append("workbook is mostly empty")
    if headers == 0:
        issues.append("workbook has no table-like rows")
    if _topic_needs_formula(topic) and formulas == 0:
        issues.append("budget/tracker workbook has no formulas")
    summary = f"Excel workbook with {len(book.sheetnames)} sheet(s), {non_empty} populated cells, and {formulas} formula cell(s)."
    return ArtifactQualityResult(
        "xlsx",
        str(path),
        not issues,
        summary,
        issues,
        validation_steps=["xlsx open", "sheet structure", "frozen pane", "formula scan"],
        delivery_ready=not issues,
    )


async def review_artifact_quality(
    db_path: str,
    artifact_type: str,
    topic: str,
    extracted: str,
) -> ArtifactQualityResult:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return ArtifactQualityResult(artifact_type, passed=True, summary="Claude review skipped: no Anthropic key.", warnings=["Claude review skipped"])
    model = os.getenv("CLAUDE_STEWARD_MODEL", CAPABILITIES["steward"].default_model)
    steward = TheSteward(os.getenv("ANTHROPIC_API_KEY", "dummy"), model)
    skill_context = artifact_skill_context(artifact_type)
    try:
        timeout = float(os.getenv("CLAUDE_ARTIFACT_REVIEW_TIMEOUT_SECONDS", "35"))
    except ValueError:
        timeout = 35
    prompt = _review_prompt(artifact_type, topic, extracted, skill_context)
    try:
        response = await asyncio.wait_for(
            steward.chat([
                {"role": "system", "content": "You are Maya's artifact quality reviewer. Return PASS: or REJECT: with concise reasons."},
                {"role": "user", "content": prompt},
            ]),
            timeout=max(10, timeout),
        )
    except Exception as exc:
        return ArtifactQualityResult(artifact_type, passed=True, summary=f"Claude review failed open: {exc}", warnings=[str(exc)])
    await record_usage(db_path, "claude_steward_calls", 1, f"{artifact_type} artifact review")
    first = response.strip().splitlines()[0] if response.strip() else ""
    rejected = first.lower().startswith("reject") or response.lower().startswith("reject")
    return ArtifactQualityResult(
        artifact_type,
        passed=not rejected,
        summary=_clip(response, 220),
        issues=[_clip(response, 300)] if rejected else [],
        review_model=model,
        validation_steps=["claude artifact skill review"],
        delivery_ready=not rejected,
    )


def extract_docx_text(path: Path, limit: int = 6000) -> str:
    from docx import Document

    doc = Document(path)
    lines = [" ".join(paragraph.text.split()) for paragraph in doc.paragraphs if paragraph.text.strip()]
    return "\n".join(lines)[:limit]


def extract_xlsx_text(path: Path, limit: int = 6000) -> str:
    from openpyxl import load_workbook

    book = load_workbook(path, data_only=False)
    lines = []
    for sheet in book.worksheets:
        lines.append(f"Sheet: {sheet.title}")
        for row in sheet.iter_rows(values_only=True):
            values = [str(value) for value in row if value not in (None, "")]
            if values:
                lines.append(" | ".join(values))
            if len("\n".join(lines)) >= limit:
                return "\n".join(lines)[:limit]
    return "\n".join(lines)[:limit]


def _review_prompt(artifact_type: str, topic: str, extracted: str, skill_context: str) -> str:
    return (
        f"Artifact type: {artifact_type}\n"
        f"User topic: {topic}\n\n"
        f"Artifact quality skill:\n{skill_context or 'No skill file found.'}\n\n"
        "Review the artifact against the skill. PASS if it is useful and deliverable. "
        "REJECT only for concrete quality failures that should stop Maya from calling it final.\n\n"
        f"Extracted artifact content:\n{extracted[:16000]}"
    )


def _summary_from_text(paragraphs: list[str], fallback: str) -> str:
    body = [item for item in paragraphs if len(item.split()) >= 4]
    if not body:
        return fallback
    joined = " ".join(body[:4])
    return _clip(joined, 260)


def _topic_needs_formula(topic: str) -> bool:
    lowered = topic.lower()
    return any(word in lowered for word in ("budget", "tracker", "expense", "total", "spend"))


def _clip(text: str, limit: int) -> str:
    clean = " ".join(str(text).split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:") + "."
