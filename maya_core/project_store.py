from __future__ import annotations

import os
import re
import json
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from retention_policy import touch_project_activity
from storage import delete_preference, get_preference, upsert_preference
from workspace_paths import project_roots as default_project_roots


ACTIVE_PROJECT_PATH = "active_project_path"
ACTIVE_PROJECT_NAME = "active_project_name"
PENDING_PROJECT_CHOICES = "pending_project_choices"


@dataclass(frozen=True)
class ProjectMatch:
    name: str
    path: Path


def project_roots() -> tuple[Path, ...]:
    raw = os.getenv("MAYA_PROJECT_ROOTS", "")
    roots = list(default_project_roots())
    for item in raw.split(","):
        if item.strip():
            roots.append(Path(item.strip()).expanduser())
    return tuple(dict.fromkeys(path.resolve() for path in roots))


async def active_project(db_path: str) -> ProjectMatch | None:
    raw_path = await get_preference(db_path, ACTIVE_PROJECT_PATH)
    raw_name = await get_preference(db_path, ACTIVE_PROJECT_NAME)
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    return ProjectMatch(raw_name or path.name, path)


async def set_active_project(db_path: str, project: ProjectMatch) -> None:
    await upsert_preference(db_path, ACTIVE_PROJECT_PATH, str(project.path), source="project")
    await upsert_preference(db_path, ACTIVE_PROJECT_NAME, project.name, source="project")
    await touch_project_activity(db_path, project.path, "opened project", "project")


async def clear_active_project(db_path: str) -> None:
    await delete_preference(db_path, ACTIVE_PROJECT_PATH)
    await delete_preference(db_path, ACTIVE_PROJECT_NAME)


async def resolve_project(name: str) -> list[ProjectMatch]:
    wanted = _norm(name)
    matches: list[ProjectMatch] = []
    for root in project_roots():
        if not root.exists():
            continue
        for child in root.iterdir():
            if child.is_dir() and _matches(wanted, child.name):
                matches.append(ProjectMatch(child.name, child.resolve()))
    return _dedupe(matches)


async def save_pending_project_choices(db_path: str, matches: list[ProjectMatch]) -> None:
    payload = [{"name": match.name, "path": str(match.path)} for match in matches[:5]]
    await upsert_preference(db_path, PENDING_PROJECT_CHOICES, json.dumps(payload), source="project")


async def clear_pending_project_choices(db_path: str) -> None:
    await delete_preference(db_path, PENDING_PROJECT_CHOICES)


async def resolve_pending_project_choice(db_path: str, text: str) -> ProjectMatch | None:
    raw = await get_preference(db_path, PENDING_PROJECT_CHOICES)
    if not raw:
        return None
    try:
        choices = json.loads(raw)
    except json.JSONDecodeError:
        await clear_pending_project_choices(db_path)
        return None
    cleaned = text.strip().lower()
    if cleaned.isdigit():
        index = int(cleaned) - 1
        if 0 <= index < len(choices):
            item = choices[index]
            return ProjectMatch(str(item["name"]), Path(str(item["path"])))
    wanted = _norm(cleaned)
    for item in choices:
        name = str(item["name"])
        path = Path(str(item["path"]))
        if _matches(wanted, name) or wanted in _norm(str(path)):
            return ProjectMatch(name, path)
    return None


async def remember_project_note(db_path: str, path: Path, kind: str, content: str) -> None:
    await _init(db_path)
    await touch_project_activity(db_path, path, f"{kind}: {content}", "project_memory")
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO project_memories (project_path, kind, content, source)
            VALUES (?, ?, ?, 'maya')
            """,
            (str(path), kind, content),
        )
        await db.commit()


async def project_notes(db_path: str, path: Path, limit: int = 5) -> list[dict[str, str]]:
    await _init(db_path)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT kind, content, source, created_at
            FROM project_memories
            WHERE project_path = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (str(path), limit),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def build_project_context(db_path: str, query: str) -> str:
    project = await active_project(db_path)
    if not project:
        return ""
    notes = await project_notes(db_path, project.path, limit=4)
    lines = [
        "Active project context:",
        f"a) name: {project.name}",
        f"b) path: {project.path}",
    ]
    for idx, note in enumerate(notes[:4], start=3):
        lines.append(f"{chr(96 + idx)}) {note['kind']}: {note['content']}")
    return "\n".join(lines)


async def _init(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS project_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_path TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT 'maya',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


def _matches(wanted: str, candidate: str) -> bool:
    current = _norm(candidate)
    return current == wanted or wanted in current or current in wanted


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _dedupe(matches: list[ProjectMatch]) -> list[ProjectMatch]:
    seen: set[str] = set()
    unique: list[ProjectMatch] = []
    for match in matches:
        key = str(match.path)
        if key not in seen:
            seen.add(key)
            unique.append(match)
    return unique
