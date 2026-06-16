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

from openpyxl import Workbook, load_workbook

from maya_documents.artifact_builder import ArtifactBuilder
from maya_core.assistant import KampungAssistant
from maya_core.context_layers import init_context_layers_db
from maya_harness.harness_artifact_store import init_harness_artifact_db
from maya_harness.harness_store import init_harness_db
from maya_core.lesson_store import init_lesson_db
from maya_core.route_tracker import last_route_text
from maya_core.routine_store import init_routine_db
from maya_core.semantic_telegram_fresh_cases import FreshCase, TARGET_CASES, build_cases
from maya_core.semantic_telegram_fresh_fakes import (
    FreshNews,
    fake_draft,
    fake_normal_route,
    fake_powerpoint_qa,
    fake_preflight,
    fake_review,
)
from maya_core.session_memory_store import init_session_memory_db
from maya_core.skill_store import init_skill_db
from maya_core.storage import get_preference, init_db


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-semantic-telegram-fresh-") as tmp:
        db_path = str(Path(tmp) / "fresh.db")
        workspace = Path(tmp) / "Maya"
        await _init(db_path)
        old_env = _capture_env()
        _set_test_env(workspace)

        import maya_documents.artifact_semantic_resolver as semantic_resolver
        import maya_documents.document_actions as da
        import maya_travel.travel_budget as travel_budget

        old_news = semantic_resolver.TheNews
        old_preflight = da.artifact_preflight_with_gemini
        old_draft = da.draft_markdown_with_gemini
        old_review = da.review_presentation_slides
        old_pptx = da.create_powerpoint_with_qa
        old_travel_draft = travel_budget.draft_markdown_with_gemini
        try:
            semantic_resolver.TheNews = FreshNews
            da.artifact_preflight_with_gemini = fake_preflight
            da.draft_markdown_with_gemini = fake_draft
            da.review_presentation_slides = fake_review
            da.create_powerpoint_with_qa = fake_powerpoint_qa
            travel_budget.draft_markdown_with_gemini = fake_draft

            assistant = KampungAssistant(db_path)
            assistant.router.route = fake_normal_route

            cases = build_cases()
            _require(len(cases) == TARGET_CASES, f"expected {TARGET_CASES} cases, got {len(cases)}")
            counts: dict[str, int] = {}
            for index, case in enumerate(cases, 1):
                response = await assistant.handle_text(
                    case.text,
                    channel="telegram",
                    input_type=case.input_type,
                    channel_external_id="fresh-telegram-smoke",
                )
                route = await last_route_text(db_path)
                await _assert_case(db_path, case, response, route, index)
                counts[case.expected] = counts.get(case.expected, 0) + 1

            await _assert_delivery_gate(db_path, workspace)
            counts["failed_qa_no_attachment"] = counts.get("failed_qa_no_attachment", 0) + 1
            print(_summary(counts))
        finally:
            semantic_resolver.TheNews = old_news
            da.artifact_preflight_with_gemini = old_preflight
            da.draft_markdown_with_gemini = old_draft
            da.review_presentation_slides = old_review
            da.create_powerpoint_with_qa = old_pptx
            travel_budget.draft_markdown_with_gemini = old_travel_draft
            _restore_env(old_env)


async def _assert_case(db_path: str, case: FreshCase, response: str, route: str, index: int) -> None:
    prefix = f"case {index} {case.expected} {case.input_type}:"
    if case.input_type == "voice note":
        _require("input: voice note" in route, f"{prefix} route did not record voice\n{route}")
        _require("xAI STT +" in route, f"{prefix} route missing STT prefix\n{route}")
    else:
        _require("input: text" in route, f"{prefix} route did not record text\n{route}")

    if case.expected in {"travel_budget", "food_budget"}:
        _require("[file:" in response, f"{prefix} expected Telegram file marker\n{response}")
        _require("travel budget notes + Local travel budget workbook" in route, f"{prefix} wrong builder\n{route}")
        _require("role-based spreadsheet draft" not in route, f"{prefix} fell to generic spreadsheet\n{route}")
        if case.expected == "food_budget":
            _require("budget-tracker" in response.lower() or "budget workbook" in response.lower(), f"{prefix} weak food budget response\n{response}")
    elif case.expected == "nontravel_budget":
        _require("[file:" in response, f"{prefix} expected nontravel workbook attachment\n{response}")
        _require("Local travel budget workbook" not in route, f"{prefix} nontravel budget used travel builder\n{route}")
    elif case.expected == "word":
        _require("[file:" in response and ".docx" in response, f"{prefix} expected Word attachment\n{response}")
        _require("Word draft" in route, f"{prefix} wrong Word route\n{route}")
    elif case.expected == "deck":
        _require("[file:" in response and ".pptx" in response, f"{prefix} expected PowerPoint attachment\n{response}")
        _require("presentation content" in route or "PowerPoint" in route, f"{prefix} wrong deck route\n{route}")
    elif case.expected == "clarify_document":
        _require("[file:" not in response, f"{prefix} clarification should not attach\n{response}")
        _require("Word doc, Excel sheet, or PowerPoint slides" in response, f"{prefix} wrong clarification\n{response}")
    elif case.expected == "edit_people":
        _require("updated the latest Excel workbook" in response, f"{prefix} expected workbook edit\n{response}")
        latest = await get_preference(db_path, "maya_last_document_path")
        _require(latest and latest.endswith(".xlsx"), f"{prefix} latest workbook missing: {latest}")
        _require("Gemini Flash text" not in route, f"{prefix} edit fell to normal chat\n{route}")
    elif case.expected == "normal_chat":
        _require("[file:" not in response, f"{prefix} normal chat created file\n{response}")
        _require("Gemini Flash text" in route, f"{prefix} normal chat did not use fake chat\n{route}")


async def _assert_delivery_gate(db_path: str, workspace: Path) -> None:
    path = workspace / "bad.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    workbook.active.title = "Sheet"
    workbook.active["A1"] = "bad"
    workbook.save(path)
    result = await ArtifactBuilder(db_path).finish_xlsx(
        path,
        "Tokyo food budget tracker",
        "telegram",
        run_id="fresh_500_delivery_gate",
        source_tool="fresh_500",
        label="an editable Tokyo food budget tracker",
    )
    _require(not result.quality.passed, "bad workbook should fail QA")
    _require("[file:" not in result.reply, f"bad workbook should not attach\n{result.reply}")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)
    await init_harness_db(db_path)
    await init_harness_artifact_db(db_path)


def _capture_env() -> dict[str, str | None]:
    keys = ("MAYA_TEST_MODE", "MAYA_TEST_ALLOW_SEMANTIC_PROVIDER", "MAYA_WORKSPACE_ROOT", "XAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY")
    return {key: os.environ.get(key) for key in keys}


def _set_test_env(workspace: Path) -> None:
    os.environ["MAYA_TEST_MODE"] = "1"
    os.environ["MAYA_TEST_ALLOW_SEMANTIC_PROVIDER"] = "1"
    os.environ["MAYA_WORKSPACE_ROOT"] = str(workspace)
    os.environ["XAI_API_KEY"] = "test-key"
    os.environ["GOOGLE_API_KEY"] = "test-key"
    os.environ.pop("ANTHROPIC_API_KEY", None)


def _restore_env(values: dict[str, str | None]) -> None:
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _summary(counts: dict[str, int]) -> str:
    parts = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    return f"semantic_telegram_fresh_500: ok ({parts})"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
