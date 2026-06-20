from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import asyncio
import argparse
import os
import re
import tempfile
from pathlib import Path

from openpyxl import load_workbook

from maya_documents.artifact_preflight import ArtifactPreflight
from maya_documents.artifact_quality import extract_docx_text, validate_docx_path
from maya_core.context_layers import init_context_layers_db
from maya_documents.document_actions import DocumentActionRouter
from maya_harness.harness_artifact_store import init_harness_artifact_db
from maya_harness.harness_store import init_harness_db
from maya_core.lesson_store import init_lesson_db
from maya_core.markdown_drafter import MarkdownDraft
from maya_core.routine_store import init_routine_db
from maya_core.session_memory_store import init_session_memory_db
from maya_core.skill_store import init_skill_db
from maya_core.storage import get_preference, init_db


class FakeBridge:
    def __init__(self) -> None:
        self.opened: list[tuple[str, str | None]] = []

    def open_file(self, path: str, app_name: str | None = None) -> None:
        self.opened.append((path, app_name))


async def main(channel: str = "all", mode: str = "full") -> None:
    with tempfile.TemporaryDirectory(prefix="maya-artifact-session-") as tmp:
        old_anthropic = os.environ.get("ANTHROPIC_API_KEY")
        os.environ.pop("ANTHROPIC_API_KEY", None)
        db_path = str(Path(tmp) / "smoke.db")
        workspace = Path(tmp) / "Maya"
        await _init(db_path)
        import maya_documents.document_actions as da

        old_draft = da.draft_markdown_with_gemini
        old_preflight = da.artifact_preflight_with_gemini
        try:
            da.draft_markdown_with_gemini = _fake_travel_draft
            da.artifact_preflight_with_gemini = _fake_preflight
            channels = ("telegram", "imac") if channel == "all" else (channel,)
            for item in channels:
                await _channel_case(db_path, workspace, item, mode=mode)
            print("artifact_session_continuity_smoke: ok")
        finally:
            da.draft_markdown_with_gemini = old_draft
            da.artifact_preflight_with_gemini = old_preflight
            _restore_env("ANTHROPIC_API_KEY", old_anthropic)


async def _channel_case(db_path: str, workspace: Path, channel: str, *, mode: str) -> None:
    bridge = FakeBridge()
    router = DocumentActionRouter(db_path, workspace=workspace, bridge=bridge)
    created = await router.handle("make me a Word document for Tokyo itinerary for two days and two people", channel)
    _require(created and ("created" in created.lower()), f"{channel} create failed: {created}")
    first_path = Path(await get_preference(db_path, "maya_last_document_path") or "")
    _require(first_path.name.startswith("tokyo-itinerary-v"), f"{channel} bad filename: {first_path.name}")
    _require(first_path.exists(), f"{channel} created file missing: {first_path}")
    first_text = extract_docx_text(first_path)
    _require("Day 1 Plan" in first_text and "Day 2 Plan" in first_text, f"{channel} initial day plan missing")
    _require("Day 3 Plan" not in first_text, f"{channel} initial document unexpectedly has Day 3")

    edited = await router.handle("change it to four days", channel)
    _require(edited and "updated" in edited.lower(), f"{channel} edit failed: {edited}")
    second_path = Path(await get_preference(db_path, "maya_last_document_path") or "")
    _require(second_path == first_path, f"{channel} edit should update same file path: {first_path} -> {second_path}")
    text = extract_docx_text(second_path)
    _require("Day 3 Plan" in text and "Day 4 Plan" in text, f"{channel} edit did not produce 4-day content:\n{text[:1200]}")
    qa = validate_docx_path(second_path, "Tokyo itinerary 4 days 2 people", doc_kind="travel_itinerary")
    _require(qa.passed, f"{channel} edited file failed 4-day QA: {qa.issues}")

    if channel == "imac":
        opened_names = [Path(path).name for path, _ in bridge.opened]
        _require(any(name.startswith("tokyo-itinerary-v") for name in opened_names), "iMac case should request Word open through fake bridge")
    else:
        _require(not bridge.opened, "telegram case should not request desktop opens")
    if mode == "canary":
        return

    budget = await router.handle("make an Excel spreadsheet for the Tokyo itinerary", channel)
    _require(budget and ("created" in budget.lower()), f"{channel} contextual Excel create failed: {budget}")
    budget_path = Path(await get_preference(db_path, "maya_last_document_path") or "")
    _require(budget_path.suffix == ".xlsx", f"{channel} latest document should be xlsx: {budget_path}")
    sheet = load_workbook(budget_path, data_only=False)["Travel Budget"]
    _require(sheet["B3"].value == 2, f"{channel} Excel did not inherit 2 travelers: {sheet['B3'].value!r}")
    if channel == "imac":
        opened_names = [Path(path).name for path, _ in bridge.opened]
        _require(any(name.startswith("tokyo-budget-tracker-v") for name in opened_names), "iMac case should request Excel open through fake bridge")


async def _fake_preflight(_db_path: str, artifact_type: str, topic: str) -> ArtifactPreflight:
    return ArtifactPreflight(artifact_type, topic, "gemini", f"{artifact_type} preflight", True)


async def _fake_travel_draft(_db_path: str, topic: str, _context: str = "") -> MarkdownDraft:
    days = _days(topic)
    sections = [
        "# Tokyo Itinerary",
        "",
        "## Trip Overview",
        "",
        f"A practical Tokyo itinerary for two people across {days} days, designed around realistic neighborhood clusters, food stops, transit timing, and backup options.",
        "The plan keeps each day focused so the travelers spend more time doing the itinerary and less time crossing the city.",
        "It uses Tokyo stations and neighborhoods as anchors, with clear daily structure and enough flexibility for queues or weather changes.",
    ]
    for day in range(1, days + 1):
        sections.extend([
            "",
            f"## Day {day} Plan",
            "",
            f"Use Day {day} for a focused Tokyo neighborhood route with a morning anchor, lunch stop, afternoon walk, dinner option, transit note, and one backup if the queue is too long.",
            f"Keep Day {day} practical by grouping stops near the same train corridor and avoiding distant single-stop detours.",
        ])
    sections.extend([
        "",
        "## Place Highlights",
        "",
        "Use Shinjuku, Shibuya, Tsukiji, Ginza, and Asakusa as flexible anchors depending on the final hotel location.",
        "Keep one market-style stop, one ramen or sushi stop, one cafe or dessert stop, and one easy dinner backup in the plan.",
        "",
        "## Budget Notes",
        "",
        f"Budget for two people across {days} days, with food, transit, attractions, and a daily buffer.",
        "Track meals, convenience-store snacks, local train rides, paid activities, and one optional splurge separately.",
        "",
        "## Booking And Transit Notes",
        "",
        "Use Suica or Pasmo, group stops by neighborhood, and stop before payment or booking submission.",
        "Check route timing before leaving each stop because transfer times and walking routes can change during the day.",
        "",
        "## Recommendations",
        "",
        "Keep each day realistic, choose backups near the same station, and avoid crossing Tokyo for one snack.",
        "Use the itinerary as a working plan and adjust the exact restaurant choice after queue, opening-hour, and hotel-location checks.",
    ])
    return MarkdownDraft("\n".join(sections), grounded=False)


def _days(topic: str) -> int:
    match = re.search(r"\b(\d{1,2}|one|two|three|four|five|six)\s*[- ]?\s*days?\b", topic.lower())
    if not match:
        return 2
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
    raw = match.group(1)
    return int(raw) if raw.isdigit() else words[raw]


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)
    await init_harness_db(db_path)
    await init_harness_artifact_db(db_path)


def _restore_env(name: str, value: str | None) -> None:
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", choices=("all", "telegram", "imac"), default="all")
    parser.add_argument("--mode", choices=("canary", "full"), default="full")
    args = parser.parse_args()
    asyncio.run(main(args.channel, args.mode))
