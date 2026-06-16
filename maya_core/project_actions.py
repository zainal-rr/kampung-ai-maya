from __future__ import annotations

import asyncio
import re
from pathlib import Path

from maya_documents.office_files import safe_slug
from maya_core.permission_policy import action_permission, path_allowed
from maya_core.retention_policy import touch_project_activity
from maya_core.project_store import (
    ProjectMatch,
    active_project,
    clear_active_project,
    clear_pending_project_choices,
    project_notes,
    remember_project_note,
    resolve_pending_project_choice,
    resolve_project,
    save_pending_project_choices,
    set_active_project,
)
from workspace_paths import workspace_dir


class ProjectActionRouter:
    def __init__(self, db_path: str, create_root: Path | None = None):
        self.db_path = db_path
        self.create_root = create_root or workspace_dir("Projects")

    async def handle(self, text: str, channel: str) -> str | None:
        selected = await resolve_pending_project_choice(self.db_path, text)
        if selected:
            await clear_pending_project_choices(self.db_path)
            await set_active_project(self.db_path, selected)
            await remember_project_note(self.db_path, selected.path, "opened", f"Opened project {selected.name}.")
            return f"Okay. I opened project {selected.name} at {selected.path}."
        command = _project_command(text)
        if command:
            return await self._handle_project_command(command)
        name = _open_project_name(text)
        if name:
            return await self.open_project(name)
        if _is_close_project(text):
            await clear_active_project(self.db_path)
            return "Okay. I closed the active project."
        if _is_project_status(text):
            return await project_status(self.db_path)
        if _is_readme_request(text):
            return await self._make_readme(channel)
        if _is_project_summary(text):
            return await self._summarize_project()
        return None

    async def open_project(self, name: str) -> str:
        matches = await resolve_project(name)
        if len(matches) == 1:
            await set_active_project(self.db_path, matches[0])
            await remember_project_note(self.db_path, matches[0].path, "opened", f"Opened project {matches[0].name}.")
            return f"Okay. I opened project {matches[0].name} at {matches[0].path}."
        if len(matches) > 1:
            await save_pending_project_choices(self.db_path, matches)
            lines = "\n".join(f"{i + 1}) {match.name} at {match.path}" for i, match in enumerate(matches[:5]))
            return "I found more than one matching project. Which one do you mean?\n" + lines
        create_path = self.create_root / safe_slug(name)
        return f"I could not find that project. Say create project {name} if you want me to make it at {create_path}."

    async def _handle_project_command(self, body: str) -> str:
        if not body:
            return await project_status(self.db_path)
        if body in {"close", "off"}:
            await clear_active_project(self.db_path)
            return "Okay. I closed the active project."
        if body.startswith(("open ", "switch ")):
            return await self.open_project(body.split(" ", 1)[1].strip())
        return await self.open_project(body)

    async def _make_readme(self, channel: str) -> str:
        project = await active_project(self.db_path)
        if not project:
            return "No active project yet. Tell me which project to open first."
        path = project.path / "README.md"
        if action_permission("write_file") != "allow" or not path_allowed(path):
            return f"I need confirmation before writing {path}."
        if path.exists():
            return f"{path} already exists. Ask me to update it if you want me to change it."
        await asyncio.to_thread(path.write_text, _readme_text(project), "utf-8")
        await remember_project_note(self.db_path, project.path, "created_file", f"Created README.md for {project.name}.")
        reply = f"Done. I created README.md for {project.name}."
        return reply + f"\n[file:{path}]" if channel == "telegram" else reply

    async def _summarize_project(self) -> str:
        project = await active_project(self.db_path)
        if not project:
            return "No active project yet. Tell me which project to open first."
        files = await asyncio.to_thread(_project_files, project.path)
        notes = await project_notes(self.db_path, project.path, limit=3)
        note_lines = "\n".join(f"{item['kind']}: {item['content']}" for item in notes) or "No project notes yet."
        return (
            f"Project: {project.name}\n"
            f"Path: {project.path}\n"
            "Visible files:\n"
            + "\n".join(f"{i + 1}) {item}" for i, item in enumerate(files[:12]))
            + f"\nProject memory:\n{note_lines}"
        )


async def project_status(db_path: str) -> str:
    project = await active_project(db_path)
    if not project:
        return "No active project right now."
    await touch_project_activity(db_path, project.path, "project status requested", "project")
    return f"Active project: {project.name}\nPath: {project.path}"


def _project_command(text: str) -> str | None:
    match = re.match(r"^/project(?:\s+(.*))?$", text.strip(), re.IGNORECASE)
    return match.group(1).strip() if match and match.group(1) else "" if match else None


def _open_project_name(text: str) -> str | None:
    match = re.match(r"^(?:open|switch to|work on|change to)(?: the)? project\s+(.+)$", text, re.IGNORECASE)
    return match.group(1).strip(" .") if match else None


def _is_close_project(text: str) -> bool:
    return " ".join(text.lower().split()) in {"close project", "close the project", "leave project"}


def _is_project_status(text: str) -> bool:
    return " ".join(text.lower().split()) in {
        "what project are we in", "which project are we in", "show project status", "active project",
    }


def _is_readme_request(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    return "readme" in lowered and ("this project" in lowered or lowered in {"make readme", "create readme"})


def _is_project_summary(text: str) -> bool:
    return " ".join(text.lower().split()) in {"summarize this project", "show project files", "project summary"}


def _readme_text(project: ProjectMatch) -> str:
    return f"# {project.name}\n\n## Overview\n\nProject notes for {project.name}.\n\n## Next Steps\n\n1) Add the first useful task.\n"


def _project_files(path: Path) -> list[str]:
    if not path.exists():
        return ["Project folder is missing."]
    return sorted(str(item.relative_to(path)) for item in path.iterdir() if item.name not in {"venv", "__pycache__"})
