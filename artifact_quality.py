from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from artifact_qa_governance import (
    MECHANICAL,
    SEMANTIC,
    QAIssue,
    blocker,
    blocker_issues,
    blocker_messages,
    legacy_blocker,
    open_world_or_semantic_blockers,
    warning_messages,
)
from cost_tracker import record_usage
from artifact_review_store import record_artifact_review, record_qa_disagreement
from models import TheSenses, TheSteward
from provider_capabilities import CAPABILITIES
from word_quality import validate_word_doc_quality_details
from word_visual_qa import inspect_word_visual_quality
from artifact_quality_extractors import (
    clip_text,
    extract_docx_text,
    extract_xlsx_text,
    food_trip_workbook,
    summary_from_text,
    topic_needs_formula,
)


SKILL_IDS = {
    "docx": "word_artifact_quality",
    "xlsx": "excel_artifact_quality",
    "pptx": "powerpoint_artifact_quality",
    "html": "html_app_artifact_quality",
}

EXTRA_SKILL_IDS = {
    "pptx": ("powerpoint_design_taste",),
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
    issue_details: list[QAIssue] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.issue_details:
            self.issues = blocker_messages(self.issue_details)
            for message in warning_messages(self.issue_details):
                if message not in self.warnings:
                    self.warnings.append(message)
        elif self.issues:
            self.issue_details = [legacy_blocker(message) for message in self.issues]
        if self.issues:
            self.passed = False
            self.delivery_ready = False

    @property
    def blocker_issue_details(self) -> list[QAIssue]:
        return blocker_issues(self.issue_details)

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
            issue_details=[*self.issue_details, *other.issue_details],
        )

    def short_issue_text(self) -> str:
        return "; ".join(self.issues[:4]) or self.summary or "quality review did not pass"


def artifact_skill_context(artifact_type: str) -> str:
    artifact_type = artifact_type.lower()
    skill_ids = [SKILL_IDS.get(artifact_type, ""), *EXTRA_SKILL_IDS.get(artifact_type, ())]
    skill_ids = [skill_id for skill_id in skill_ids if skill_id]
    if not skill_ids:
        return ""
    chunks = []
    for skill_id in skill_ids:
        text = _skill_text(skill_id)
        if text:
            chunks.append(text)
    return "\n\n".join(chunks)[:16000]


def _skill_text(skill_id: str) -> str:
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
        issue_details=[legacy_blocker(issue, "html.structure") for issue in issues],
        validation_steps=["html structure", "interactive controls", "common syntax corruption"],
        delivery_ready=not issues,
    )


def validate_docx_path(path: Path, topic: str = "") -> ArtifactQualityResult:
    from docx import Document

    issues: list[str] = []
    issue_details: list[QAIssue] = []
    paragraphs: list[str] = []
    headings: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current_heading = ""
    try:
        doc = Document(path)
    except Exception as exc:
        message = f"Word file could not be opened: {exc}"
        return ArtifactQualityResult("docx", str(path), False, issues=[message], issue_details=[legacy_blocker(message, "docx.open")], delivery_ready=False)
    for paragraph in doc.paragraphs:
        text = " ".join(paragraph.text.split())
        if not text:
            continue
        paragraphs.append(text)
        style_name = getattr(getattr(paragraph, "style", None), "name", "")
        if "heading" in style_name.lower():
            headings.append(text)
            current_heading = text
            sections.append((current_heading, []))
        elif current_heading and sections:
            sections[-1][1].append(text)
    word_count = sum(len(item.split()) for item in paragraphs)
    joined = "\n".join(paragraphs).lower()
    if word_count < 40:
        issue_details.append(legacy_blocker("document has too little real content", "docx.content_density"))
    if not headings:
        issue_details.append(legacy_blocker("document has no useful headings", "docx.headings_missing"))
    bad = ("lorem ipsum", "todo", "placeholder section", "placeholder text", "draft document about", "add a specific point", "```", "###")
    issue_details.extend(legacy_blocker(f"placeholder or malformed text found: {marker}", "docx.placeholder_scan") for marker in bad if marker in joined)
    issue_details.extend(validate_word_doc_quality_details(topic, paragraphs, headings, sections))
    visual = inspect_word_visual_quality(path)
    issue_details.extend(legacy_blocker(issue, "docx.visual_layout") for issue in visual.issues)
    issues = blocker_messages(issue_details)
    summary = summary_from_text(paragraphs, "Word document")
    return ArtifactQualityResult(
        "docx",
        str(path),
        not issues,
        summary,
        issues,
        visual.warnings,
        validation_steps=["docx open", "headings", "content density", "placeholder scan", "word visual layout"],
        delivery_ready=not issues,
        issue_details=issue_details,
    )


def validate_xlsx_path(path: Path, topic: str = "") -> ArtifactQualityResult:
    from openpyxl import load_workbook

    issues: list[str] = []
    issue_details: list[QAIssue] = []
    try:
        book = load_workbook(path, data_only=False)
    except Exception as exc:
        message = f"Excel file could not be opened: {exc}"
        return ArtifactQualityResult("xlsx", str(path), False, issues=[message], issue_details=[legacy_blocker(message, "xlsx.open")], delivery_ready=False)
    if not book.sheetnames:
        issue_details.append(legacy_blocker("workbook has no sheets", "xlsx.sheet_missing"))
    non_empty = 0
    formulas = 0
    headers = 0
    workbook_text: list[str] = []
    for sheet in book.worksheets:
        if sheet.title.lower() in {"sheet", "sheet1", "maya draft"}:
            issue_details.append(legacy_blocker(f"{sheet.title} is not a meaningful sheet name", "xlsx.sheet_name"))
        if sheet.max_row < 3 or sheet.max_column < 2:
            issue_details.append(legacy_blocker(f"{sheet.title} has too little structure", "xlsx.structure"))
        if not sheet.freeze_panes:
            issue_details.append(legacy_blocker(f"{sheet.title} has no frozen header/reference pane", "xlsx.freeze_panes"))
        for row in sheet.iter_rows(values_only=True):
            values = [value for value in row if value not in (None, "")]
            if values:
                workbook_text.extend(str(value) for value in values)
                non_empty += len(values)
                if len(values) >= 3:
                    headers += 1
            formulas += sum(1 for value in values if isinstance(value, str) and value.startswith("="))
    if non_empty < 8:
        issue_details.append(legacy_blocker("workbook is mostly empty", "xlsx.content_density"))
    if headers == 0:
        issue_details.append(legacy_blocker("workbook has no table-like rows", "xlsx.table_rows"))
    if topic_needs_formula(topic) and formulas == 0:
        issue_details.append(legacy_blocker("budget/tracker workbook has no formulas", "xlsx.formulas_missing"))
    lowered = " ".join(workbook_text).lower()
    if topic_needs_formula(topic):
        for required in ("estimated", "actual", "variance"):
            if required not in lowered:
                issue_details.append(legacy_blocker(f"budget/tracker workbook missing {required} column or field", "xlsx.required_budget_field"))
    if food_trip_workbook(topic):
        for required in ("restaurant", "estimated", "actual", "variance", "source", "suggestion"):
            if required not in lowered:
                issue_details.append(legacy_blocker(f"food-trip workbook missing {required} detail", "xlsx.required_food_trip_field"))
    issues = blocker_messages(issue_details)
    summary = f"Excel workbook with {len(book.sheetnames)} sheet(s), {non_empty} populated cells, and {formulas} formula cell(s)."
    return ArtifactQualityResult(
        "xlsx",
        str(path),
        not issues,
        summary,
        issues,
        validation_steps=["xlsx open", "sheet structure", "frozen pane", "formula scan"],
        delivery_ready=not issues,
        issue_details=issue_details,
    )


async def resolve_quality_disagreement(
    db_path: str,
    *,
    artifact_type: str,
    topic: str,
    path: Path,
    local_qa: ArtifactQualityResult,
    review_qa: ArtifactQualityResult,
    extracted: str,
    attempt_number: int = 1,
) -> ArtifactQualityResult:
    """Demote validator false positives only when semantic review and arbiter agree."""
    disputed = open_world_or_semantic_blockers(local_qa.issue_details)
    if not disputed or not review_qa.passed:
        return local_qa
    adjusted = local_qa
    for issue in disputed:
        verdict, evidence = await _arbitrate_validator_claim(db_path, artifact_type, topic, issue, extracted)
        if verdict == "validator_wrong":
            adjusted = _demote_issue(adjusted, issue, evidence)
            await record_qa_disagreement(
                db_path,
                artifact_type=artifact_type,
                topic=topic,
                artifact_path=str(path),
                rule_id=issue.rule_id,
                rule_class=issue.rule_class,
                severity=issue.severity,
                validator_verdict="fail",
                reviewer_verdict="pass",
                arbiter_verdict="validator_wrong",
                attempt_number=attempt_number,
                final_action="delivered_cleanly_with_audit",
                evidence=evidence,
            )
        else:
            await record_qa_disagreement(
                db_path,
                artifact_type=artifact_type,
                topic=topic,
                artifact_path=str(path),
                rule_id=issue.rule_id,
                rule_class=issue.rule_class,
                severity=issue.severity,
                validator_verdict="fail",
                reviewer_verdict="pass",
                arbiter_verdict=verdict,
                attempt_number=attempt_number,
                final_action="validator_upheld",
                evidence=evidence,
            )
    return adjusted


async def _arbitrate_validator_claim(
    db_path: str,
    artifact_type: str,
    topic: str,
    issue: QAIssue,
    extracted: str,
) -> tuple[str, str]:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "arbiter_unavailable", "Gemini arbitration skipped: GOOGLE_API_KEY missing."
    model = os.getenv("GEMINI_FLASH_MODEL", "gemini-3-flash-preview")
    senses = TheSenses(api_key, model)
    prompt = (
        "You are Maya's targeted QA arbiter. Do not judge general quality. "
        "Judge only this validator claim against the provided artifact text.\n\n"
        f"Artifact type: {artifact_type}\n"
        f"User topic: {topic}\n"
        f"Validator rule: {issue.rule_id}\n"
        f"Validator class: {issue.rule_class}\n"
        f"Validator claim: {issue.message}\n"
        f"Validator evidence: {issue.evidence or '(none)'}\n\n"
        "Answer exactly one label first:\n"
        "VALIDATOR_CORRECT — the validator claim is true enough to block or repair.\n"
        "VALIDATOR_WRONG — the validator claim is false or too ambiguous to block.\n"
        "Then add one short reason.\n\n"
        f"Artifact text:\n{extracted[:12000]}"
    )
    try:
        timeout = float(os.getenv("GEMINI_QA_ARBITER_TIMEOUT_SECONDS", "25"))
    except ValueError:
        timeout = 25
    try:
        reply = await asyncio.wait_for(
            senses.chat([
                {"role": "system", "content": "Return VALIDATOR_CORRECT or VALIDATOR_WRONG first."},
                {"role": "user", "content": prompt},
            ]),
            timeout=max(8, timeout),
        )
    except Exception as exc:
        return "arbiter_unavailable", f"Gemini arbitration failed: {type(exc).__name__}"
    await record_usage(db_path, "gemini_flash_text_calls", 1, f"{artifact_type} QA arbiter")
    first = reply.strip().splitlines()[0].strip().upper() if reply.strip() else ""
    if first.startswith("VALIDATOR_WRONG"):
        return "validator_wrong", clip_text(reply, 400)
    if first.startswith("VALIDATOR_CORRECT"):
        return "validator_correct", clip_text(reply, 400)
    lowered = reply.lower()
    if "validator_wrong" in lowered or "validator is wrong" in lowered:
        return "validator_wrong", clip_text(reply, 400)
    return "validator_correct", clip_text(reply or "Gemini did not return a clear label.", 400)


def _demote_issue(result: ArtifactQualityResult, target: QAIssue, evidence: str) -> ArtifactQualityResult:
    details = [
        issue.demote_to_warning(evidence) if issue == target else issue
        for issue in result.issue_details
    ]
    return ArtifactQualityResult(
        artifact_type=result.artifact_type,
        path=result.path,
        passed=True,
        summary=result.summary,
        warnings=[*result.warnings],
        draft_model=result.draft_model,
        review_model=result.review_model,
        validation_steps=[*result.validation_steps, "gemini targeted QA arbitration"],
        repair_attempted=result.repair_attempted,
        delivery_ready=True,
        issue_details=details,
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
        return ArtifactQualityResult(
            artifact_type,
            passed=True,
            summary="Claude review unavailable; local validation is the delivery gate for this artifact.",
            warnings=[f"Claude review failed open: {type(exc).__name__}"],
        )
    await record_usage(db_path, "claude_steward_calls", 1, f"{artifact_type} artifact review")
    first = response.strip().splitlines()[0] if response.strip() else ""
    rejected = first.lower().startswith("reject") or response.lower().startswith("reject")
    await record_artifact_review(db_path, artifact_type, topic, model, not rejected, response)
    return ArtifactQualityResult(
        artifact_type,
        passed=not rejected,
        summary=clip_text(response, 220),
        issues=[clip_text(response, 300)] if rejected else [],
        issue_details=[blocker("review.semantic_reject", SEMANTIC, clip_text(response, 300))] if rejected else [],
        review_model=model,
        validation_steps=["claude artifact skill review"],
        delivery_ready=not rejected,
    )


def _review_prompt(artifact_type: str, topic: str, extracted: str, skill_context: str) -> str:
    return (
        f"Artifact type: {artifact_type}\n"
        f"User topic: {topic}\n\n"
        f"Artifact quality skill:\n{skill_context or 'No skill file found.'}\n\n"
        "Review the artifact against the skill. PASS if it is useful and deliverable. "
        "REJECT only for concrete quality failures that should stop Maya from calling it final. "
        "Do not claim visual styling, rendered layout, sheet count, or chart quality unless those facts are present in the extracted artifact content. "
        "For spreadsheets, distinguish worksheets from sections inside one worksheet.\n\n"
        f"Extracted artifact content:\n{extracted[:16000]}"
    )
