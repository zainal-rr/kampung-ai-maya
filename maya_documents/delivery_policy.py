from __future__ import annotations

from maya_documents.artifact_qa_governance import BLOCKER, MECHANICAL


_COMMON_HARD_MARKERS = (
    "could not be opened",
    "cannot be opened",
    "file could not be opened",
    "corrupt",
    "unsafe path",
    "path traversal",
    "outside allowed",
    "permission denied",
    "permission error",
    "overwrite",
    "manual edit",
)


def excel_quality_hard_block(quality) -> bool:
    text = _mechanical_quality_text(quality)
    hard_markers = (
        *_COMMON_HARD_MARKERS,
        "formula",
        "broken",
        "workbook has no sheets",
        "cannot recalculate",
    )
    return any(marker in text for marker in hard_markers)


def docx_quality_hard_block(quality) -> bool:
    text = _mechanical_quality_text(quality)
    hard_markers = (
        *_COMMON_HARD_MARKERS,
        "empty document",
        "no paragraphs",
    )
    return any(marker in text for marker in hard_markers)


def pptx_quality_hard_block(quality) -> bool:
    text = _mechanical_quality_text(quality)
    hard_markers = (
        *_COMMON_HARD_MARKERS,
        "deck has no slides",
        "no slides",
    )
    return any(marker in text for marker in hard_markers)


def _mechanical_quality_text(quality) -> str:
    details = list(getattr(quality, "issue_details", None) or [])
    if details:
        parts = [
            f"{issue.rule_id} {issue.message} {issue.evidence}"
            for issue in details
            if getattr(issue, "severity", "") == BLOCKER
            and getattr(issue, "rule_class", "") == MECHANICAL
        ]
        return " ".join(parts).lower()
    return _quality_text(quality)


def _quality_text(quality) -> str:
    parts: list[str] = []
    for attr in ("issues", "warnings", "notes"):
        value = getattr(quality, attr, None)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
    for attr in ("summary", "polish"):
        value = getattr(quality, attr, "")
        if callable(value):
            try:
                value = value()
            except Exception:
                value = ""
        if value:
            parts.append(str(value))
    short = getattr(quality, "short_issue_text", None)
    if callable(short):
        try:
            parts.append(str(short()))
        except Exception:
            pass
    return " ".join(parts).lower()
