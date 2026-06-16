from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


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
            named_artifact_path(root, "a 3 day Tokyo trip", "docx").name == "tokyo-itinerary-v1.docx",
            "day count should not leak into document filenames",
        )
        _require(
            named_artifact_path(root, "of a travel planner app", "html").name == "travel-app-v1.html",
            "filename should stay short and concept-first",
        )
        _require(
            named_artifact_path(root, "quick editable budget tracker for Tokyo", "xlsx").name
            == "tokyo-budget-tracker-v1.xlsx",
            "filename should keep subject and purpose, not quality words",
        )
        _require(
            named_artifact_path(root, "2-day Seoul food trip. Save it as a real docx file.", "docx").name
            == "seoul-itinerary-v1.docx",
            "delivery instructions and day counts should not leak into filenames",
        )
        _require(
            named_artifact_path(root, "travel planner app as a real html file", "html").name
            == "travel-app-v1.html",
            "format instructions should not leak into filenames",
        )
        _require(
            named_artifact_path(
                root,
                "2-day Seoul food trip. Include itinerary, food highlights, budget notes, and recommendations.",
                "pptx",
            ).name
            == "seoul-deck-v1.pptx",
            "include clauses should not leak into PowerPoint filenames",
        )
        _require(
            named_artifact_path(
                root,
                "Seoul food trip planner app. It should let me add restaurants, budget, notes, and mark places as visited.",
                "html",
            ).name
            == "seoul-app-v1.html",
            "behavior requirement clauses should not leak into HTML filenames",
        )
        _require(
            named_artifact_path(root, "make me a router config", "docx").name == "router-config-v1.docx",
            "router config should use two meaningful words",
        )
        _require(
            named_artifact_path(root, "both chicken shawarma and nasi lemak recipes in a Word document", "docx").name
            == "shawarma-nasi-lemak-v1.docx",
            "recipe filenames should use the dishes, not generic 'both document'",
        )
        _require(
            named_artifact_path(root, "put all the recipes and ingredients in Word document", "docx").name
            == "recipes-v1.docx",
            "generic recipe filenames should not use filler words like all/both",
        )
    print("artifact_naming_smoke: ok")


if __name__ == "__main__":
    main()
