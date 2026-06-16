from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import os
import tempfile
from pathlib import Path

from docx import Document
from openpyxl import Workbook

import artifact_quality_review
from artifact_qa_governance import MECHANICAL, OPEN_WORLD, SEMANTIC, blocker, warning
from artifact_quality import ArtifactQualityResult, resolve_quality_disagreement, validate_docx_path, validate_xlsx_path
from artifact_retry_policy import artifact_qa_max_attempts
from artifact_review_store import (
    latest_artifact_review_text,
    record_artifact_review,
    resolve_review_activity_text,
)
from word_quality_travel import destination_consistency_issue_details


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _write_docx(path: Path, sections: list[tuple[str, list[str]]]) -> None:
    doc = Document()
    doc.add_heading(path.stem.replace("-", " ").title(), level=1)
    for heading, paragraphs in sections:
        doc.add_heading(heading, level=2)
        for paragraph in paragraphs:
            doc.add_paragraph(paragraph)
    doc.save(path)


async def _main() -> None:
    old_attempts = os.environ.pop("ARTIFACT_QA_MAX_ATTEMPTS", None)
    old_docx_attempts = os.environ.pop("DOCX_QA_MAX_ATTEMPTS", None)
    try:
        _require(artifact_qa_max_attempts("docx") == 3, "default QA attempts should be 3")
    finally:
        _restore_env("ARTIFACT_QA_MAX_ATTEMPTS", old_attempts)
        _restore_env("DOCX_QA_MAX_ATTEMPTS", old_docx_attempts)

    with tempfile.TemporaryDirectory(prefix="maya-artifact-governance-") as tmp:
        root = Path(tmp)
        good = root / "kazakhstan.docx"
        _write_docx(good, _kazakhstan_sections(include_day_5=True))
        good_quality = validate_docx_path(good, "make a nine day Kazakhstan itinerary doc", doc_kind="travel_itinerary")
        _require(good_quality.passed, good_quality.short_issue_text())
        _require(not any("destination mismatch" in issue for issue in good_quality.issues), "Almaty must not fail Kazakhstan")

        missing_day = root / "kazakhstan-missing-day.docx"
        _write_docx(missing_day, _kazakhstan_sections(include_day_5=False))
        missing_quality = validate_docx_path(missing_day, "make a nine day Kazakhstan itinerary doc", doc_kind="travel_itinerary")
        _require(not missing_quality.passed, "missing day must block")
        _require(any("Day 5 Plan" in issue for issue in missing_quality.issues), missing_quality.issues)

        drift = destination_consistency_issue_details(
            "make a nine day Kazakhstan itinerary doc",
            ["Tokyo food crawl and Shibuya evening plan."],
            ["Tokyo Day 1 Plan"],
        )
        _require(any(issue.blocks_delivery for issue in drift), "clear outside-country drift should block")

        ambiguous = destination_consistency_issue_details(
            "make a three day Atlantis itinerary doc",
            ["Arrival and museum walk."],
            ["Day 1 Plan"],
        )
        _require(ambiguous and not any(issue.blocks_delivery for issue in ambiguous), "ambiguous open-world destination should warn only")

        db_path = str(root / "session_history.db")
        target = blocker("travel.destination_match", OPEN_WORLD, "travel document destination mismatch: expected Kazakhstan, found Almaty")
        local = ArtifactQualityResult("docx", str(good), False, "local failed", issue_details=[target])
        review = ArtifactQualityResult("docx", str(good), True, "PASS: semantically valid.", review_model="fake-claude")
        old_arbiter = artifact_quality_review._arbitrate_validator_claim

        async def fake_arbiter(*_args, **_kwargs):
            return "validator_wrong", "VALIDATOR_WRONG: Almaty is valid Kazakhstan context."

        artifact_quality_review._arbitrate_validator_claim = fake_arbiter
        try:
            adjusted = await resolve_quality_disagreement(
                db_path,
                artifact_type="docx",
                topic="nine day Kazakhstan itinerary",
                path=good,
                local_qa=local,
                review_qa=review,
                extracted="Almaty is part of Kazakhstan.",
                attempt_number=1,
            )
        finally:
            artifact_quality_review._arbitrate_validator_claim = old_arbiter
        _require(adjusted.passed, adjusted.short_issue_text())
        _require(adjusted.warnings, "demoted issue should become warning")

        confirmed = blocker(
            "travel.destination_match",
            OPEN_WORLD,
            "travel document destination mismatch: expected Kazakhstan, found Tokyo",
            evidence="Title says Tokyo Day 1 Plan and no Kazakhstan places appear.",
        )
        local_confirmed = ArtifactQualityResult("docx", str(good), False, "local failed", issue_details=[confirmed])

        async def validator_correct_arbiter(*_args, **_kwargs):
            return "validator_correct", "VALIDATOR_CORRECT: The document is about Tokyo, not Kazakhstan."

        artifact_quality_review._arbitrate_validator_claim = validator_correct_arbiter
        try:
            upheld = await resolve_quality_disagreement(
                db_path,
                artifact_type="docx",
                topic="nine day Kazakhstan itinerary",
                path=good,
                local_qa=local_confirmed,
                review_qa=review,
                extracted="Tokyo Day 1 Plan\nShibuya and Ginza itinerary.",
                attempt_number=2,
            )
        finally:
            artifact_quality_review._arbitrate_validator_claim = old_arbiter
        _require(not upheld.passed, "Gemini-confirmed validator issue must stay blocking")
        _require(upheld.issues == [confirmed.message], upheld.issues)

        warning_only = ArtifactQualityResult(
            "docx",
            str(good),
            True,
            "warning-only result",
            issue_details=[warning("docx.destination_note", SEMANTIC, "city-level destination wording should be reviewed")],
        )
        _require(warning_only.passed, "warnings must not block delivery")
        _require(not warning_only.issues and warning_only.warnings, "warning-only result should expose warnings, not issues")

        bad_budget = root / "bad-budget.xlsx"
        _write_formula_free_budget(bad_budget)
        bad_budget_quality = validate_xlsx_path(bad_budget, "monthly budget tracker for home")
        _require(not bad_budget_quality.passed, "budget workbook without formulas must block")
        _require(
            any(issue.rule_id == "xlsx.formulas_missing" and issue.rule_class == MECHANICAL for issue in bad_budget_quality.issue_details),
            [issue.rule_id for issue in bad_budget_quality.issue_details],
        )

        await record_artifact_review(db_path, "docx", "nine day Kazakhstan itinerary", "fake-claude", True, "PASS: good.")
        text = await latest_artifact_review_text(db_path)
        _require("QA disagreements" in text and "travel.destination_match" in text, text)
        resolved = await resolve_review_activity_text(db_path, "review 1 is resolved")
        _require(resolved and "Marked review 1 as resolved" in resolved, str(resolved))
        text = await latest_artifact_review_text(db_path)
        _require("~~1." in text or "~~1)" in text, "resolved review item should be crossed out")

        empty_db_path = str(root / "empty_session_history.db")
        empty_resolve = await resolve_review_activity_text(empty_db_path, "review 1 is resolved")
        _require(empty_resolve == "There are no QA disagreement review items to resolve this week.", str(empty_resolve))

    print("artifact_qa_governance_smoke: ok")


def _kazakhstan_sections(*, include_day_5: bool) -> list[tuple[str, list[str]]]:
    sections = [
        ("Trip Overview", ["This Kazakhstan itinerary balances Almaty nature access, city logistics, and mountain day trips for a practical nine day journey."]),
    ]
    for day in range(1, 10):
        if day == 5 and not include_day_5:
            continue
        place = "Almaty" if day <= 4 else "Astana" if day >= 8 else "Charyn Canyon"
        sections.append((
            f"Day {day} Plan",
            [
                f"Start in {place} with one primary activity, one flexible backup, and clear transit pacing for the day.",
                "Keep the schedule realistic, with morning movement, afternoon exploration, and a simple evening review of costs and energy.",
            ],
        ))
    sections.extend([
        ("Place Highlights", ["Almaty, Charyn Canyon, Kolsai Lakes, and Astana give the trip a mix of nature, architecture, and easy recovery days."]),
        ("Budget Notes", ["Track flights, hotels, local drivers, park access, meals, insurance, and contingency in one simple travel budget."]),
        ("Booking And Transit Notes", ["Use Almaty as the nature base, confirm driver availability early, and leave buffer time before domestic transfers."]),
        ("Recommendations", ["Choose fewer bases, protect hiking days from overpacking, and keep one flexible day for weather changes."]),
    ])
    return sections


def _write_formula_free_budget(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Home Budget"
    sheet.freeze_panes = "A2"
    sheet.append(["Category", "Item", "Estimated", "Actual", "Variance"])
    sheet.append(["Housing", "Rent", 1000, 950, 50])
    sheet.append(["Food", "Groceries", 500, 520, -20])
    sheet.append(["Transport", "Fuel", 300, 280, 20])
    workbook.save(path)


def _restore_env(key: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(key, None)
    else:
        os.environ[key] = value


if __name__ == "__main__":
    asyncio.run(_main())
