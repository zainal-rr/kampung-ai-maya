from __future__ import annotations

import re
from pathlib import Path

from maya_documents.artifact_qa_governance import (
    QAIssue,
    blocker_messages,
    legacy_blocker,
)
from maya_documents.artifact_quality_core import ArtifactQualityResult, artifact_skill_context
from word_quality import validate_word_doc_quality_details
from word_visual_qa import inspect_word_visual_quality
from maya_documents.artifact_quality_extractors import (
    extract_docx_text,
    extract_xlsx_text,
    food_trip_workbook,
    summary_from_text,
    topic_needs_formula,
)


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


def validate_docx_path(path: Path, topic: str = "", *, doc_kind: str = "generic_document") -> ArtifactQualityResult:
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
    issue_details.extend(validate_word_doc_quality_details(topic, paragraphs, headings, sections, doc_kind=doc_kind))
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


from maya_documents.artifact_quality_review import resolve_quality_disagreement, review_artifact_quality
