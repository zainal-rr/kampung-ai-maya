from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from artifact_quality import validate_docx_path, validate_html_content, validate_xlsx_path
from artifact_quality_extractors import topic_needs_formula
from document_actions_content_helpers import _task_tracker_rows
from office_modern_files import create_docx, create_xlsx
from powerpoint_quality_context import powerpoint_quality_context
from skill_evaluator import evaluate_skill_scaffold


SKILLS = (
    "word_artifact_quality",
    "excel_artifact_quality",
    "powerpoint_artifact_quality",
    "powerpoint_design_taste",
    "html_app_artifact_quality",
)


async def main() -> None:
    _skill_smoke()
    skill_context = await powerpoint_quality_context(":memory:")
    _require("PowerPoint Artifact Quality" in skill_context, "PowerPoint quality context missing")
    _require("PowerPoint Design Taste" in skill_context, "PowerPoint design taste context missing")
    _require("Design Engineering" in skill_context, "Design Engineering context missing from PowerPoint QA")
    with tempfile.TemporaryDirectory(prefix="maya-artifact-quality-") as tmp:
        root = Path(tmp)
        docx = create_docx(
            root / "quality.docx",
            "Quality Plan",
            [
                ("Role And Assumptions", ["Maya creates this document for a real user who needs a usable artifact."]),
                ("Plan", ["The document has enough concrete content, useful headings, and no generic filler."]),
                ("Review Checklist", ["Openability, headings, density, and malformed markdown are checked before delivery."]),
            ],
        )
        xlsx = create_xlsx(
            root / "budget.xlsx",
            "Budget Tracker",
            ["Category", "Estimated", "Actual", "Variance"],
            [["Flights", 100, 90, "=C4-B4"], ["Total", "=SUM(B4:B4)", "=SUM(C4:C4)", "=SUM(D4:D4)"]],
        )
        task_headers, task_rows = _task_tracker_rows("office task tracker with owner due date status priority")
        task_xlsx = create_xlsx(root / "task-tracker.xlsx", "Office Task Tracker", task_headers, task_rows)
        good_html = (
            "<!DOCTYPE html><html><head><style>body{font-family:system-ui}</style></head>"
            "<body><main><input id='x'><button id='b'>Save</button></main>"
            "<script>document.getElementById('b').addEventListener('click',()=>localStorage.setItem('x',document.getElementById('x').value));</script>"
            "</body></html>"
        )
        bad_html = "<.DOCTYPE html><html><head><style>body{font family:system ui}</style></head><body></body></html>"
        _require(validate_docx_path(docx).passed, "docx quality should pass")
        _require(validate_xlsx_path(xlsx, "budget tracker").passed, "xlsx quality should pass")
        _require(validate_xlsx_path(task_xlsx, "office task tracker with owner due date status priority").passed, "task tracker xlsx should pass")
        _require(topic_needs_formula("Seoul food trip budget tracker"), "budget trackers should require formulas")
        _require(not topic_needs_formula("office task tracker with owner due date status priority"), "non-budget task tracker should not require budget formulas")
        _require(validate_html_content("planner", good_html).passed, "html quality should pass")
        _require(not validate_html_content("planner", bad_html).passed, "broken html quality should fail")
    print("artifact_quality_smoke: ok")


def _skill_smoke() -> None:
    for skill_id in SKILLS:
        path = Path("maya_skills") / "active" / f"{skill_id}.md"
        results = evaluate_skill_scaffold(str(path))
        failed = [name for name, (status, _) in results.items() if status != "passed"]
        _require(not failed, f"{skill_id} failed skill scaffold checks: {failed}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
