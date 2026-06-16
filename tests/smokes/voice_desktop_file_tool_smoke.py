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

from maya_core.context_layers import init_context_layers_db
from maya_harness.harness_artifact_store import init_harness_artifact_db
from maya_harness.harness_store import init_harness_db
from maya_core.lesson_store import init_lesson_db
from maya_core.markdown_drafter import MarkdownDraft
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db
from xai_realtime_document_tools import execute_desktop_file_tool


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-voice-file-tool-") as tmp:
        os.environ["MAYA_TEST_MODE"] = "1"
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        db_path = str(Path(tmp) / "smoke.db")
        await _init(db_path)

        import maya_documents.document_actions as da

        old_draft = da.draft_markdown_with_gemini
        old_should = da.should_use_model_draft
        try:
            da.draft_markdown_with_gemini = _fake_draft
            da.should_use_model_draft = lambda topic: True
            first = await execute_desktop_file_tool(db_path, "create an md file about router setup")
            second = await execute_desktop_file_tool(db_path, "create an md file about router setup")
            md_files = sorted(path.name for path in Path(os.environ["MAYA_WORKSPACE_ROOT"]).rglob("*.md"))
            _require(md_files == ["router-setup-v1.md", "router-setup-v2.md"], f"unexpected versioned names: {md_files}")
            _require("opened it" in first.lower() and "opened it" in second.lower(), "versioned Markdown files did not open")

            request = (
                "make an Excel budget spreadsheet for a trip to Kyoto and Osaka starting August 30th "
                "including categories for flights accommodation food transportation attractions miscellaneous "
                "with columns for estimated cost actual cost and notes plus a total summary at the bottom"
            )
            reply = await execute_desktop_file_tool(db_path, request)
            files = list(Path(os.environ["MAYA_WORKSPACE_ROOT"]).rglob("*.xlsx"))
            _require(files, "long voice Excel request did not create a workbook")
            _require(len(files[0].name) < 120, "voice workbook filename was not shortened")
            _require("opened it" in reply.lower(), "voice tool did not return an opened-file response")
            print("voice_desktop_file_tool_smoke: ok")
        finally:
            da.draft_markdown_with_gemini = old_draft
            da.should_use_model_draft = old_should


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)
    await init_harness_db(db_path)
    await init_harness_artifact_db(db_path)


async def _fake_draft(db_path: str, topic: str) -> MarkdownDraft:
    return MarkdownDraft(f"# {topic.title()}\n\n## Budget\n\n1) Created from voice request.\n")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
