from __future__ import annotations

import tempfile
from pathlib import Path

from artifact_naming import named_artifact_path


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-artifact-naming-") as tmp:
        root = Path(tmp)
        _require(
            named_artifact_path(root, "a 3 day Tokyo trip", "docx").name == "3-day-tokyo-trip-v1.docx",
            "leading article should be removed from document filenames",
        )
        _require(
            named_artifact_path(root, "of a travel planner app", "html").name == "travel-planner-app-v1.html",
            "leading connector phrase should be removed from HTML filenames",
        )
        _require(
            named_artifact_path(root, "quick editable budget tracker for Tokyo", "xlsx").name
            == "editable-budget-tracker-for-tokyo-v1.xlsx",
            "only weak leading quality words should be removed",
        )
        _require(
            named_artifact_path(root, "2-day Seoul food trip. Save it as a real docx file.", "docx").name
            == "2-day-seoul-food-trip-v1.docx",
            "delivery instructions should not leak into filenames",
        )
        _require(
            named_artifact_path(root, "travel planner app as a real html file", "html").name
            == "travel-planner-app-v1.html",
            "format instructions should not leak into filenames",
        )
        _require(
            named_artifact_path(
                root,
                "2-day Seoul food trip. Include itinerary, food highlights, budget notes, and recommendations.",
                "pptx",
            ).name
            == "2-day-seoul-food-trip-v1.pptx",
            "include clauses should not leak into PowerPoint filenames",
        )
        _require(
            named_artifact_path(
                root,
                "Seoul food trip planner app. It should let me add restaurants, budget, notes, and mark places as visited.",
                "html",
            ).name
            == "seoul-food-trip-planner-app-v1.html",
            "behavior requirement clauses should not leak into HTML filenames",
        )
    print("artifact_naming_smoke: ok")


if __name__ == "__main__":
    main()
