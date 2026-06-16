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

from maya_documents.artifact_preflight import ArtifactPreflight
from maya_documents.artifact_quality import ArtifactQualityResult
from document_actions import DocumentActionRouter
from document_actions_context import LAST_DOC_KEY
from document_actions_smoke_helpers import _init, _require
from office_modern_files import create_docx
from storage import upsert_preference
from telegram_delivery import split_file_markers


async def _fake_preflight(db_path: str, artifact_type: str, topic: str) -> ArtifactPreflight:
    return ArtifactPreflight(artifact_type, topic, "local", "fake preflight", False)


async def _fake_artifact_review(db_path: str, artifact_type: str, topic: str, content: str) -> ArtifactQualityResult:
    return ArtifactQualityResult(
        artifact_type,
        passed=True,
        summary="fake Word review passed",
        review_model="claude-opus-4-8",
        validation_steps=["fake Word review"],
    )


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-word-edit-") as tmp:
        old_google = os.environ.pop("GOOGLE_API_KEY", None)
        old_anthropic = os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)

        import document_actions as da

        old_preflight = da.artifact_preflight_with_gemini
        old_review = da.review_artifact_quality
        da.artifact_preflight_with_gemini = _fake_preflight
        da.review_artifact_quality = _fake_artifact_review
        try:
            path = Path(tmp) / "Maya" / "documents" / "seoul-food-trip-v1.docx"
            create_docx(path, "Seoul Food Trip", _travel_sections())
            await upsert_preference(db_path, LAST_DOC_KEY, str(path), source="smoke")
            router = DocumentActionRouter(db_path, workspace=Path(tmp) / "Maya")
            reply = await router.handle("update that document to include transit tips", "telegram")
            text, files = split_file_markers(reply or "")
            _require("Done. I updated" in text, "simple Word edit did not finish")
            _require(files and files[0].resolve() == path.resolve(), "successful Word edit did not attach updated file")
            from maya_documents.artifact_quality_extractors import extract_docx_text

            updated = extract_docx_text(path)
            _require("Transit Tips" in updated, "transit tips section missing")
            _require("Naver Maps" in updated and "T-money" in updated, "Seoul transit detail missing")
        finally:
            da.artifact_preflight_with_gemini = old_preflight
            da.review_artifact_quality = old_review
            if old_google is not None:
                os.environ["GOOGLE_API_KEY"] = old_google
            if old_anthropic is not None:
                os.environ["ANTHROPIC_API_KEY"] = old_anthropic


def _travel_sections() -> list[tuple[str, list[str]]]:
    return [
        ("Trip Overview", ["A compact 2-day Seoul food itinerary focused on classic meals, cafes, and manageable neighborhoods."]),
        ("Day 1 Plan", ["Start in Myeongdong, move to Gwangjang Market, and keep dinner flexible around Jongno or Ikseon-dong."]),
        ("Day 2 Plan", ["Use Seongsu cafes in the morning, then keep a dinner slot for Korean BBQ or a soup stop."]),
        ("Food And Restaurant Highlights", ["Myeongdong Kyoja, Gwangjang Market, Cafe Onion, and Maple Tree House give a useful mix."]),
        ("Budget Notes", ["Plan separate cash for street food, one larger dinner, cafe stops, and a small queue-time buffer."]),
        ("Booking And Transit Notes", ["Use Naver Maps for transfers, keep T-money ready, and group stops by neighborhood."]),
        ("Recommendations", ["Avoid peak queues, keep a backup cafe, and do not cross Seoul for one snack unless it is a priority."]),
    ]


if __name__ == "__main__":
    asyncio.run(main())
