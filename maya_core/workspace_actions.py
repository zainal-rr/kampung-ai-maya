from __future__ import annotations

import asyncio
import re
from pathlib import Path

from maya_documents.office_files import safe_slug
from permission_policy import action_permission, path_allowed
from project_store import ProjectMatch, remember_project_note, set_active_project
from workspace_paths import ensure_workspace_tree, workspace_dir


class WorkspaceActionRouter:
    def __init__(self, workspace: Path | None = None, db_path: str | None = None):
        self.workspace = workspace or workspace_dir("")
        self.projects_root = self.workspace / "Projects"
        self.db_path = db_path

    async def handle(self, text: str, channel: str) -> str | None:
        folder_name = _folder_name(text)
        if folder_name:
            return await self._create_folder(folder_name)
        project_name = _project_name(text)
        if project_name:
            return await self._create_project(project_name)
        return None

    async def _create_folder(self, name: str) -> str:
        ensure_workspace_tree()
        path = self.workspace / safe_slug(name)
        if action_permission("create_file") != "allow" or not path_allowed(path):
            return f"I need confirmation before creating {path}."
        await asyncio.to_thread(path.mkdir, parents=True, exist_ok=True)
        return f"Done. I created the folder at {path}."

    async def _create_project(self, name: str) -> str:
        ensure_workspace_tree()
        path = self.projects_root / safe_slug(name)
        if action_permission("create_file") != "allow" or not path_allowed(path):
            return f"I need confirmation before creating {path}."
        await asyncio.to_thread(_make_project, path, name)
        if self.db_path:
            project = ProjectMatch(path.name, path.resolve())
            await set_active_project(self.db_path, project)
            await remember_project_note(self.db_path, project.path, "created", f"Created project {project.name}.")
        return f"Done. I created the project at {path} with a starter README."


def _make_project(path: Path, name: str) -> None:
    for folder in (path, path / "docs", path / "src", path / "assets"):
        folder.mkdir(parents=True, exist_ok=True)
    readme = path / "README.md"
    if not readme.exists():
        readme.write_text(
            f"# {name.strip().title()}\n\n"
            "Created by Maya.\n\n"
            "## Notes\n\n"
            "Add the first useful idea here.\n",
            encoding="utf-8",
        )


def _folder_name(text: str) -> str | None:
    match = re.match(
        r"^(?:create|make|start)(?: a)? folder(?: called| named| for)?\s+(.+)$",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return _clean_name(match.group(1))


def _project_name(text: str) -> str | None:
    match = re.match(
        r"^(?:create|make|start)(?: a)? project(?: called| named| for)?\s+(.+)$",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return _clean_name(match.group(1))


def _clean_name(name: str) -> str:
    return re.sub(r"\s+(?:in|on)\s+(?:my\s+)?i?mac$", "", name, flags=re.IGNORECASE).strip(" .")
