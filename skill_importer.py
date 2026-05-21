from __future__ import annotations

import re
import shutil
from pathlib import Path

from security_manifest import SecurityManifest, upsert_manifest
from skill_learning_store import upsert_skill_metadata
from skill_library import proposed_path
from skill_store import create_skill_proposal, init_skill_db, upsert_skill


async def import_local_skill(db_path: str, folder: str) -> str:
    source_dir = Path(folder).expanduser()
    skill_file = source_dir / "SKILL.md"
    if not skill_file.exists():
        return "I could not find SKILL.md in that folder."
    text = skill_file.read_text("utf-8")
    name = _extract_name(text, source_dir.name)
    skill_id = _slug(name)
    destination = proposed_path(skill_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(skill_file, destination)
    description = _extract_description(text)
    triggers = _extract_list(text, "trigger")
    tools = _extract_list(text, "tool")
    permissions = _permission_guess(text)
    await init_skill_db(db_path)
    await upsert_skill(
        db_path, skill_id, name, description, "review_required", "approval_required",
        "proposed", "imported", str(destination),
    )
    await create_skill_proposal(
        db_path, skill_id, f"Import skill from {source_dir}", f"Imported skill: {name}",
        "Review imported instructions, manifest, and tests before activation.", str(destination),
    )
    await upsert_skill_metadata(
        db_path, skill_id, triggers=triggers, tools_needed=tools,
        safety_boundary="Imported skill. Review and test before activation.",
        review_notes="Imported as proposed only.",
    )
    await upsert_manifest(
        db_path,
        SecurityManifest(
            "skill", skill_id, permissions,
            hard_blocks=["private_exposure", "secrets", "auto_activation"],
            notes="Imported skill manifest inferred from SKILL.md.",
        ),
    )
    return f"Imported {name} as a proposed skill. It is not active yet."


def parse_skill_summary(path: str) -> dict[str, object]:
    text = Path(path).read_text("utf-8")
    return {
        "name": _extract_name(text, Path(path).parent.name),
        "description": _extract_description(text),
        "triggers": _extract_list(text, "trigger"),
        "tools": _extract_list(text, "tool"),
        "permissions": _permission_guess(text),
    }


def _extract_name(text: str, fallback: str) -> str:
    for pattern in (r"^#\s+(.+)$", r"(?im)^name:\s*(.+)$"):
        match = re.search(pattern, text, re.MULTILINE)
        if match:
            return match.group(1).strip()[:80]
    return fallback.replace("_", " ").replace("-", " ").title()


def _extract_description(text: str) -> str:
    match = re.search(r"(?im)^description:\s*(.+)$", text)
    if match:
        return match.group(1).strip()[:300]
    body = re.sub(r"^#.*$", "", text, count=1, flags=re.MULTILINE).strip()
    return " ".join(body.split())[:300] or "Imported skill."


def _extract_list(text: str, keyword: str) -> list[str]:
    lines = []
    capture = False
    for raw in text.splitlines():
        low = raw.lower()
        if keyword in low and (low.startswith("#") or low.endswith(":")):
            capture = True
            continue
        if capture and raw.startswith("#"):
            break
        if capture and raw.strip().startswith(("-", "*")):
            lines.append(raw.strip(" -*")[:120])
    return lines[:10]


def _permission_guess(text: str) -> dict[str, bool]:
    low = text.lower()
    return {
        "read_files": any(word in low for word in ("read file", "inspect file", "open file")),
        "write_files": any(word in low for word in ("write file", "edit file", "create file")),
        "browse_web": any(word in low for word in ("browser", "web", "url", "search")),
        "browser_click": "click" in low,
        "form_fill": "form" in low or "fill" in low,
        "external_api": "api" in low,
        "write_memory": "memory" in low,
        "create_artifacts": any(word in low for word in ("document", "artifact", "report", "file")),
    }


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "imported_skill"
