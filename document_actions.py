from __future__ import annotations

import asyncio
import re
from pathlib import Path

from office_files import create_docx, create_pptx, presentation_outline, safe_slug
from permission_policy import action_permission, contains_sensitive_info, hard_no_private_exposure_text, path_allowed
from project_store import active_project, remember_project_note
from storage import get_preference, upsert_preference
from utils import OSBridge


LAST_DOC_KEY = "maya_last_document_path"


class DocumentActionRouter:
    def __init__(self, db_path: str, workspace: Path | None = None, bridge: OSBridge | None = None):
        self.db_path = db_path
        self.workspace = workspace or Path.home() / "Downloads" / "Kampung AI"
        self.bridge = bridge or OSBridge()

    async def handle(self, text: str, channel: str) -> str | None:
        update = _markdown_update(text)
        if update:
            return await self._update_markdown(update, channel)
        request = _document_request(text)
        if request is None:
            return None
        kind, topic, project_scoped = request
        if project_scoped and not await active_project(self.db_path):
            return "No active project yet. Open or create a project first, then I can put it under that project's docs folder."
        if contains_sensitive_info(topic):
            return hard_no_private_exposure_text()
        if action_permission("create_document" if kind != "pptx" else "create_presentation") != "allow":
            return "I need your confirmation before creating that document."
        if kind == "md":
            return await self._create_markdown(topic, project_scoped, channel)
        if kind == "docx":
            return await self._create_word(topic, project_scoped, channel)
        return await self._create_powerpoint(topic, channel)

    async def _create_markdown(self, topic: str, project_scoped: bool, channel: str) -> str:
        path = await self._path("md", topic, project_scoped)
        content = _markdown_content(topic)
        if not path_allowed(path):
            return f"I can't write to {path}."
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_text, content, "utf-8")
        await self._remember(path, "Created Markdown draft", project_scoped)
        return await self._done("Markdown draft", path, channel, app_name=None)

    async def _create_word(self, topic: str, project_scoped: bool, channel: str) -> str:
        path = await self._path("docx", topic, project_scoped)
        if not path_allowed(path):
            return f"I can't write to {path}."
        await asyncio.to_thread(create_docx, path, topic.title(), _doc_sections(topic))
        await self._remember(path, "Created Word draft", project_scoped)
        return await self._done("Word draft", path, channel, "Microsoft Word")

    async def _create_powerpoint(self, topic: str, channel: str) -> str:
        path = self.workspace / "presentations" / f"{safe_slug(topic)}.pptx"
        if not path_allowed(path):
            return f"I can't write to {path}."
        await asyncio.to_thread(create_pptx, path, topic.title(), presentation_outline(topic))
        await upsert_preference(self.db_path, LAST_DOC_KEY, str(path), source="document")
        return await self._done("PowerPoint draft", path, channel, "Microsoft PowerPoint")

    async def _update_markdown(self, note: str, channel: str) -> str:
        path = await self._markdown_target()
        if path is None:
            return "Tell me which Markdown file to update first."
        if contains_sensitive_info(note):
            return hard_no_private_exposure_text()
        if path.suffix.lower() != ".md":
            return "The last document is not a Markdown file, so I will not edit it this way."
        addition = f"\n\n## Update\n\n{note.strip()}\n"
        await asyncio.to_thread(_append_text, path, addition)
        await upsert_preference(self.db_path, LAST_DOC_KEY, str(path), source="document")
        return _attach(f"Done. I updated the Markdown file at {path}.", path, channel)

    async def _path(self, kind: str, topic: str, project_scoped: bool) -> Path:
        project = await active_project(self.db_path) if project_scoped else None
        if project:
            return project.path / "docs" / f"{safe_slug(topic)}.{kind}"
        folder = "notes" if kind == "md" else "documents"
        return self.workspace / folder / f"{safe_slug(topic)}.{kind}"

    async def _remember(self, path: Path, action: str, project_scoped: bool) -> None:
        await upsert_preference(self.db_path, LAST_DOC_KEY, str(path), source="document")
        project = await active_project(self.db_path) if project_scoped else None
        if project:
            await remember_project_note(self.db_path, project.path, "document", f"{action}: {path.name}")

    async def _done(self, label: str, path: Path, channel: str, app_name: str | None) -> str:
        message = f"Done. I created a {label} at {path}."
        if channel == "imac":
            try:
                await asyncio.to_thread(self.bridge.open_file, str(path), app_name)
                return f"{message} I opened it on the iMac."
            except Exception as exc:
                return f"{message} I could not open it: {exc}"
        return _attach(message, path, channel)

    async def _markdown_target(self) -> Path | None:
        raw = await get_preference(self.db_path, LAST_DOC_KEY)
        return Path(raw) if raw else None


def _document_request(text: str) -> tuple[str, str, bool] | None:
    cleaned = " ".join(text.strip().split())
    patterns = (
        (r"^(?:create|make|write)\s+(?:an?\s+)?(?:md|markdown)(?: file| note)?(?: for this project)?\s+(?:about|on|for)?\s*(.+)$", "md"),
        (r"^(?:create|make|write)\s+(?:a\s+)?(?:word document|docx|document)(?: for this project)?\s+(?:about|on|for)?\s*(.+)$", "docx"),
        (r"^(?:make|create|craft)\s+(?:a\s+)?(?:presentation|pptx|slides)\s+(?:on|about|for)\s+(.+)$", "pptx"),
    )
    for pattern, kind in patterns:
        match = re.match(pattern, cleaned, re.IGNORECASE)
        if match:
            return kind, _clean_topic(match.group(1)), "this project" in cleaned.lower()
    return None


def _markdown_update(text: str) -> str | None:
    match = re.match(r"^(?:update|append to|add to)\s+(?:this\s+)?(?:markdown|md)(?: file)?\s+(?:with|about)?\s*(.+)$", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _clean_topic(topic: str) -> str:
    return topic.strip(" .") or "maya-notes"


def _markdown_content(topic: str) -> str:
    title = topic.strip().title()
    return f"# {title}\n\n## Overview\n\nDraft notes about {topic.strip()}.\n\n## Key Points\n\n1) Add the first important point.\n2) Add supporting detail.\n\n## Next Steps\n\n1) Review and refine this draft.\n"


def _doc_sections(topic: str) -> list[tuple[str, list[str]]]:
    return [
        ("Overview", [f"Draft document about {topic.strip()}."]),
        ("Key Points", ["Add the main point.", "Add supporting evidence.", "Add practical implications."]),
        ("Next Steps", ["Review the draft.", "Add missing details.", "Decide what should be polished next."]),
    ]


def _append_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def _attach(message: str, path: Path, channel: str) -> str:
    return f"{message}\n[file:{path}]" if channel == "telegram" else message
