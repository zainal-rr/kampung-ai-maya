from __future__ import annotations

import asyncio
import os
import tempfile
import zipfile
from pathlib import Path

from assistant import KampungAssistant
from context_layers import init_context_layers_db
from lesson_store import init_lesson_db
from project_store import active_project
from routine_store import init_routine_db
from session_memory_store import init_session_memory_db
from skill_store import init_skill_db
from storage import init_db
from telegram_delivery import split_file_markers


class FakeBridge:
    def __init__(self):
        self.opened: list[tuple[str, str | None]] = []

    def open_file(self, path: str, app_name: str | None = None) -> None:
        self.opened.append((path, app_name))


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-doc-actions-") as tmp:
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        db_path = str(Path(tmp) / "smoke.db")
        root = Path(tmp) / "projects"
        (root / "orchid-lab").mkdir(parents=True)
        os.environ["MAYA_PROJECT_ROOTS"] = str(root)
        await _init(db_path)
        assistant = KampungAssistant(db_path)
        bridge = FakeBridge()
        assistant.commands.documents.bridge = bridge
        assistant.commands.documents.workspace = Path(tmp) / "Maya"

        md = await assistant.handle_text("create an md file about router setup", "telegram")
        _, md_files = split_file_markers(md)
        _require(md_files and md_files[0].suffix == ".md" and md_files[0].exists(), "markdown file missing")

        docx = await assistant.handle_text("write a Word document about router setup", "telegram")
        _, docx_files = split_file_markers(docx)
        _require(docx_files and _zip_has(docx_files[0], "word/document.xml"), "docx file missing")

        deck = await assistant.handle_text("make presentation on router setup", "telegram")
        _, deck_files = split_file_markers(deck)
        _require(deck_files and _zip_has(deck_files[0], "ppt/presentation.xml"), "pptx file missing")

        await assistant.handle_text("open project Orchid Lab", "telegram")
        project = await active_project(db_path)
        _require(project is not None, "project did not open")
        scoped = await assistant.handle_text("create an md file for this project about setup", "telegram")
        _, scoped_files = split_file_markers(scoped)
        _require(
            scoped_files and scoped_files[0].parent.resolve() == (project.path / "docs").resolve(),
            "project md not in docs",
        )

        updated = await assistant.handle_text("update this markdown with add cable notes", "telegram")
        _require("updated the Markdown file" in updated, "markdown update failed")
        _require("add cable notes" in scoped_files[0].read_text(encoding="utf-8"), "markdown update not written")

        blocked = await assistant.handle_text("create an md file about API key token", "telegram")
        _require("can't expose sensitive" in blocked.lower(), "sensitive document was not blocked")

        imac = await assistant.handle_text("write a Word document about desk setup", "imac")
        _require("opened it on the iMac" in imac and bridge.opened, "iMac document did not open")
        print("document_actions_smoke: ok")


async def _init(db_path: str) -> None:
    await init_db(db_path)
    await init_lesson_db(db_path)
    await init_skill_db(db_path)
    await init_routine_db(db_path)
    await init_session_memory_db(db_path)
    await init_context_layers_db(db_path)


def _zip_has(path: Path, member: str) -> bool:
    with zipfile.ZipFile(path) as archive:
        return member in archive.namelist()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    asyncio.run(main())
