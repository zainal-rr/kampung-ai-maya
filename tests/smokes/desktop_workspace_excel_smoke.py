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
import zipfile
from pathlib import Path

from markdown_drafter import MarkdownDraft
from openpyxl import load_workbook


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-desktop-workspace-") as tmp:
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        from maya_core.assistant import KampungAssistant
        from context_layers import init_context_layers_db
        from lesson_store import init_lesson_db
        from routine_store import init_routine_db
        from session_memory_store import init_session_memory_db
        from skill_store import init_skill_db
        from storage import init_db
        from telegram_delivery import split_file_markers
        from workspace_paths import ensure_workspace_tree, workspace_dir
        from harness_artifact_store import latest_artifacts
        import document_actions

        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path, init_db, init_lesson_db, init_skill_db, init_routine_db, init_session_memory_db, init_context_layers_db)
        root = ensure_workspace_tree()
        _require((root / "spreadsheets").is_dir(), "spreadsheets folder missing")
        assistant = KampungAssistant(db_path)
        old_draft = document_actions.draft_markdown_with_gemini
        old_should = document_actions.should_use_model_draft
        document_actions.draft_markdown_with_gemini = _fake_draft
        document_actions.should_use_model_draft = lambda topic: True

        try:
            excel = await assistant.handle_text("make an Excel tracker for Kampung AI cost", "telegram")
            _, excel_files = split_file_markers(excel)
            _require(not excel_files, "retired Kampung AI cost workbook should not be created")
            _require("/cost" in excel, "retired Kampung AI cost workbook should point to /cost")
            artifacts = await latest_artifacts(db_path)
            _require(not any(item["kind"] == "spreadsheet" for item in artifacts), "retired cost workbook should not be tracked")

            md = await assistant.handle_text("create an md file about daily notes", "telegram")
            _, md_files = split_file_markers(md)
            _require(md_files and md_files[0].parent.resolve() == workspace_dir("notes").resolve(), "md not in notes")

            blocked = await assistant.handle_text("make an Excel sheet about API key token", "telegram")
            _require("can't expose sensitive" in blocked.lower(), "sensitive xlsx was not blocked")
        finally:
            document_actions.draft_markdown_with_gemini = old_draft
            document_actions.should_use_model_draft = old_should
    print("desktop_workspace_excel_smoke: ok")


async def _init(db_path: str, *initializers) -> None:
    for initializer in initializers:
        await initializer(db_path)


def _zip_has(path: Path, member: str) -> bool:
    with zipfile.ZipFile(path) as archive:
        return member in archive.namelist()


def _workbook_text(path: Path) -> str:
    book = load_workbook(path, data_only=False)
    values = []
    for sheet in book.worksheets:
        for row in sheet.iter_rows(values_only=True):
            values.extend(str(item) for item in row if item is not None)
    return "\n".join(values)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def _fake_draft(db_path: str, topic: str) -> MarkdownDraft:
    return MarkdownDraft(f"# {topic.title()}\n\n## Draft\n\n1) Item one.\n2) Item two.\n", grounded=False)


if __name__ == "__main__":
    asyncio.run(main())
