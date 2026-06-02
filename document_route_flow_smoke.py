from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from context_layers import init_context_layers_db
from harness_artifact_store import init_harness_artifact_db
from harness_store import init_harness_db
from lesson_store import init_lesson_db
from artifact_preflight import ArtifactPreflight
from markdown_drafter import MarkdownDraft
from route_tracker import last_route_text
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db
from xai_realtime_document_tools import execute_desktop_file_tool


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-doc-route-flow-") as tmp:
        os.environ["MAYA_TEST_MODE"] = "1"
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)

        import document_actions as da
        import travel_budget

        old_draft = da.draft_markdown_with_gemini
        old_review = da.review_presentation_slides
        old_preflight = da.artifact_preflight_with_gemini
        old_travel_draft = travel_budget.draft_markdown_with_gemini
        try:
            da.draft_markdown_with_gemini = _fake_draft
            da.review_presentation_slides = _fake_review
            da.artifact_preflight_with_gemini = _fake_preflight
            travel_budget.draft_markdown_with_gemini = _fake_draft

            await _case(db_path, "create an md file about drone operations", "Gemini Flash role-based document draft")
            await _case(db_path, "write a Word document about drone company operations", "Gemini artifact preflight + Gemini Flash role-based Word draft")
            await _case(db_path, "make an Excel spreadsheet about drone inspection pipeline", "Gemini artifact preflight + Gemini Flash role-based spreadsheet draft")
            await _case(db_path, "make an Excel travel budget sheet for Osaka trip", "Gemini artifact preflight + Gemini Flash role-based travel budget notes + Local travel budget workbook")
            await _case(
                db_path,
                "make presentation on drone inspection company",
                "Gemini artifact preflight + PowerPoint design taste + Gemini Flash role-based presentation content + Claude presentation design review",
            )
            print("document_route_flow_smoke: ok")
        finally:
            da.draft_markdown_with_gemini = old_draft
            da.review_presentation_slides = old_review
            da.artifact_preflight_with_gemini = old_preflight
            travel_budget.draft_markdown_with_gemini = old_travel_draft


async def _case(db_path: str, request: str, expected_lane: str) -> None:
    reply = await execute_desktop_file_tool(db_path, request)
    _require("created" in reply.lower(), f"request did not create file: {request}")
    route = await last_route_text(db_path)
    _require("input: voice" in route, f"route input was not voice: {route}")
    _require("create_desktop_maya_file" in route, f"voice file tool missing in route: {route}")
    _require(expected_lane in route, f"expected lane missing: {expected_lane}\n{route}")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)
    await init_harness_db(db_path)
    await init_harness_artifact_db(db_path)


async def _fake_draft(db_path: str, topic: str, preflight_context: str = "") -> MarkdownDraft:
    return MarkdownDraft(
        "# Role Based Draft\n\n"
        "## Role And Assumptions\n\n"
        "1) I am the operator who must use this artifact.\n\n"
        "## Key Decisions\n\n"
        "1) Cover the practical workflow.\n\n"
        "## Risks\n\n"
        "1) Confirm assumptions before acting.\n",
        grounded=False,
    )


async def _fake_review(db_path: str, topic: str, slides):
    return [("Designed Story Arc", ["Preserve Gemini content", "Improve slide rhythm"])]


async def _fake_preflight(db_path: str, artifact_type: str, topic: str) -> ArtifactPreflight:
    return ArtifactPreflight(artifact_type, topic, "gemini", "runtime preflight", True)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
