from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from artifact_preflight import ArtifactPreflight
from document_actions import DocumentActionRouter
from markdown_drafter import MarkdownDraft
from office_modern_files import create_pptx
from pptx_quality_gate import PptxQualityResult
from storage import init_db
from telegram_delivery import split_file_markers


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-pptx-reject-") as tmp:
        old_root = os.environ.get("MAYA_WORKSPACE_ROOT")
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        db_path = str(Path(tmp) / "test.db")
        await init_db(db_path)
        import document_actions as da

        old_draft = da.draft_markdown_with_gemini
        old_should = da.should_use_model_draft
        old_preflight = da.artifact_preflight_with_gemini
        old_review = da.review_presentation_slides
        old_create = da.create_powerpoint_with_qa

        async def fake_draft(db_path: str, topic: str, preflight_context: str = "") -> MarkdownDraft:
            return MarkdownDraft("# Seoul Food Trip\n\n## Plan\n\n1) Food-first route.\n")

        async def fake_preflight(db_path: str, artifact_type: str, topic: str) -> ArtifactPreflight:
            return ArtifactPreflight(artifact_type, topic, "local", "pptx blueprint", False)

        async def fake_review(db_path: str, topic: str, slides):
            return slides

        async def fake_create(db_path: str, path: Path, title: str, slides, run_id: str, last_doc_key: str, auto_improve: bool = True, visual_image_max: int | None = None):
            create_pptx(path, title, slides)
            return PptxQualityResult(False, ["slide 2 has truncated text"], [], 0, "")

        da.draft_markdown_with_gemini = fake_draft
        da.should_use_model_draft = lambda topic: True
        da.artifact_preflight_with_gemini = fake_preflight
        da.review_presentation_slides = fake_review
        da.create_powerpoint_with_qa = fake_create
        try:
            router = DocumentActionRouter(db_path, workspace=Path(tmp) / "Maya")
            reply = await router.handle("make me a Seoul food trip deck in PowerPoint", "telegram")
            clean_reply, markers = split_file_markers(reply or "")
            # Current delivery policy: a QA-rejected deck is still attached,
            # but only with an explicit honest not-final warning so the user
            # can inspect it without mistaking it for an accepted artifact.
            _require(markers, "rejected PPTX should attach the draft for inspection")
            _require(
                "not calling it final" in clean_reply.lower(),
                "rejected PPTX delivery must carry the honest not-final warning",
            )
        finally:
            da.draft_markdown_with_gemini = old_draft
            da.should_use_model_draft = old_should
            da.artifact_preflight_with_gemini = old_preflight
            da.review_presentation_slides = old_review
            da.create_powerpoint_with_qa = old_create
            if old_root is None:
                os.environ.pop("MAYA_WORKSPACE_ROOT", None)
            else:
                os.environ["MAYA_WORKSPACE_ROOT"] = old_root
    print("pptx_rejected_delivery_smoke: ok")


def _require(condition, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
