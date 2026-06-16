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

from openpyxl import load_workbook

from maya_core.context_layers import init_context_layers_db
from harness_artifact_store import init_harness_artifact_db
from harness_store import init_harness_db
from lesson_store import init_lesson_db
from maya_documents.artifact_preflight import ArtifactPreflight
from markdown_drafter import MarkdownDraft
from route_tracker import last_route_text
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import get_preference
from storage import init_db
from xai_realtime_document_tools import execute_desktop_file_tool


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-doc-route-flow-") as tmp:
        os.environ["MAYA_TEST_MODE"] = "1"
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)

        import maya_documents.document_actions as da
        import maya_documents.artifact_semantic_resolver as semantic_resolver
        import travel_budget

        old_draft = da.draft_markdown_with_gemini
        old_review = da.review_presentation_slides
        old_preflight = da.artifact_preflight_with_gemini
        old_news = semantic_resolver.TheNews
        old_travel_draft = travel_budget.draft_markdown_with_gemini
        old_allow_semantic = os.environ.get("MAYA_TEST_ALLOW_SEMANTIC_PROVIDER")
        old_xai = os.environ.get("XAI_API_KEY")
        try:
            da.draft_markdown_with_gemini = _fake_draft
            da.review_presentation_slides = _fake_review
            da.artifact_preflight_with_gemini = _fake_preflight
            semantic_resolver.TheNews = _FakeNews
            travel_budget.draft_markdown_with_gemini = _fake_draft

            await _case(db_path, "create an md file about drone operations", "Gemini Flash role-based document draft")
            await _case(db_path, "write a Word document about drone company operations", "Gemini artifact preflight + Gemini Flash role-based Word draft")
            await _case(db_path, "make an Excel spreadsheet about drone inspection pipeline", "Gemini artifact preflight + Gemini Flash role-based spreadsheet draft")
            await _case(db_path, "make an Excel travel budget sheet for Osaka trip", "Gemini artifact preflight + Gemini Flash role-based travel budget notes + Local travel budget workbook")
            await _case(
                db_path,
                "make me a two days food budget tracker in Excel? it is for Tokyo and for two days. the number of people is two.",
                "Gemini artifact preflight + Gemini Flash role-based travel budget notes + Local travel budget workbook",
            )
            await _case(
                db_path,
                "create an excel sheet for Tokyo meals, 2 days, 2 pax",
                "Gemini artifact preflight + Gemini Flash role-based travel budget notes + Local travel budget workbook",
            )
            await _case(
                db_path,
                "create an Excel sheet for Tokyo Mills two days two pack?",
                "Gemini artifact preflight + Gemini Flash role-based travel budget notes + Local travel budget workbook",
            )
            await _case(
                db_path,
                "create an Excel sheet for Tokyo Mails two days, two packs?",
                "Gemini artifact preflight + Gemini Flash role-based travel budget notes + Local travel budget workbook",
            )
            await _edit_case(
                db_path,
                "In a Tokyo dining cost tracker, today's number of people is 2.",
                "Gemini artifact preflight + local Excel edit",
                expected_people=2,
            )
            await _case(
                db_path,
                "Put my Tokyo restaurant spending plan in Excel for 2 days and 2 adult.",
                "Gemini artifact preflight + Gemini Flash role-based travel budget notes + Local travel budget workbook",
            )
            await _clarification_case(db_path, "A Tokyo food cost sheet.")
            os.environ["MAYA_TEST_ALLOW_SEMANTIC_PROVIDER"] = "1"
            os.environ["XAI_API_KEY"] = "test-key"
            await _case(
                db_path,
                "A Tokyo food cost sheet.",
                "Grok semantic artifact router + Gemini artifact preflight + Gemini Flash role-based travel budget notes + Local travel budget workbook",
            )
            await _case(
                db_path,
                "Give me a Tokyo Excel sheet for 2 days with 2 people.",
                "Grok semantic artifact router + Gemini artifact preflight + Gemini Flash role-based travel budget notes + Local travel budget workbook",
            )
            await _edit_case(
                db_path,
                "change it to two person now?",
                "Gemini artifact preflight + local Excel edit",
                expected_people=2,
            )
            os.environ.pop("MAYA_TEST_ALLOW_SEMANTIC_PROVIDER", None)
            await _clarification_case(db_path, "make me a Seoul food trip document.", expected_text="Word doc, Excel sheet, or PowerPoint slides")
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
            semantic_resolver.TheNews = old_news
            _restore_env("MAYA_TEST_ALLOW_SEMANTIC_PROVIDER", old_allow_semantic)
            _restore_env("XAI_API_KEY", old_xai)
            travel_budget.draft_markdown_with_gemini = old_travel_draft


async def _case(db_path: str, request: str, expected_lane: str) -> None:
    reply = await execute_desktop_file_tool(db_path, request)
    _require("created" in reply.lower(), f"request did not create file: {request}")
    route = await last_route_text(db_path)
    _require("input: voice" in route, f"route input was not voice: {route}")
    _require("create_desktop_maya_file" in route, f"voice file tool missing in route: {route}")
    _require(expected_lane in route, f"expected lane missing: {expected_lane}\n{route}")


async def _edit_case(db_path: str, request: str, expected_lane: str, *, expected_people: int) -> None:
    reply = await execute_desktop_file_tool(db_path, request)
    _require("updated" in reply.lower(), f"request did not update latest file: {request}\n{reply}")
    route = await last_route_text(db_path)
    _require("input: voice" in route, f"route input was not voice: {route}")
    _require("create_desktop_maya_file" in route, f"voice file tool missing in route: {route}")
    _require(expected_lane in route, f"expected edit lane missing: {expected_lane}\n{route}")
    raw = await get_preference(db_path, "maya_last_document_path")
    _require(raw and raw.endswith(".xlsx"), f"latest document should remain xlsx after edit: {raw}")
    sheet = load_workbook(raw, data_only=False)["Travel Budget"]
    _require(sheet["B3"].value == expected_people, f"people count not edited in workbook: {sheet['B3'].value!r}")


async def _clarification_case(db_path: str, request: str, *, expected_text: str = "Do you want me to create") -> None:
    reply = await execute_desktop_file_tool(db_path, request)
    _require(expected_text in reply, f"artifact fragment did not ask clarification: {reply}")
    route = await last_route_text(db_path)
    _require("clarification" in route, f"clarification route missing: {route}")


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
        "# Drone Company Operations Guide\n\n"
        "## Overview\n\n"
        "This guide defines how a drone inspection team plans jobs, assigns pilots, checks airspace constraints, captures site evidence, and hands results to the client without losing safety or documentation quality.\n\n"
        "## Key Points\n\n"
        "The coordinator confirms the site address, weather window, pilot roster, battery count, sensor payload, and client deliverable before field work starts. The pilot performs a pre-flight checklist, records takeoff conditions, captures required angles, and logs exceptions before leaving site.\n\n"
        "## Recommended Approach\n\n"
        "Every job should include flight logs, battery records, image/video coverage notes, incident notes, and a client-ready summary. Missing coverage, unsafe weather, or unclear access permission must stop final delivery until the issue is resolved.\n\n"
        "## Risks\n\n"
        "Store raw media, processed inspection outputs, and client notes in the project folder. Send only verified deliverables, and keep restricted site details out of public channels.\n\n"
        "## Next Steps\n\n"
        "Assign one owner for the next inspection run, confirm the aircraft and payload, prepare the client checklist, and run a short post-job review after delivery.\n",
        grounded=False,
    )


async def _fake_review(db_path: str, topic: str, slides):
    return [("Designed Story Arc", ["Preserve Gemini content", "Improve slide rhythm"])]


async def _fake_preflight(db_path: str, artifact_type: str, topic: str) -> ArtifactPreflight:
    return ArtifactPreflight(artifact_type, topic, "gemini", "runtime preflight", True)


class _FakeNews:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def chat(self, messages):
        text = messages[-1]["content"].lower()
        if "food cost sheet" in text:
            return (
                '{"action":"create","kind":"xlsx","topic":"Tokyo food cost tracker",'
                '"instruction":"Tokyo food cost tracker","question":"","save_copy":false}'
            )
        if "excel sheet" in text:
            return (
                '{"action":"create","kind":"xlsx","topic":"Tokyo",'
                '"instruction":"Tokyo Excel sheet","question":"","save_copy":false}'
            )
        return '{"action":"none","kind":"","topic":"","instruction":"","question":"","save_copy":false}'


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
