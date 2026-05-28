from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
from pathlib import Path

from security_manifest import SecurityManifest, upsert_manifest
from skill_learning_store import upsert_skill_metadata
from skill_library import proposed_path
from skill_store import create_skill_proposal, init_skill_db, upsert_skill


NPX_SKILL_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


async def import_local_skill(db_path: str, folder: str) -> str:
    source_dir = Path(folder).expanduser()
    skill_file = source_dir / "SKILL.md"
    if not skill_file.exists():
        return "I could not find SKILL.md in that folder."
    return await _import_skill_file(db_path, skill_file, f"Import skill from {source_dir}")


async def import_npx_skill(db_path: str, package: str) -> str:
    package = package.strip()
    if not NPX_SKILL_PATTERN.match(package):
        return "I can only import npx skills from a simple owner/repo name for now."
    with tempfile.TemporaryDirectory(prefix="maya_npx_skill_") as tmpdir:
        ok, message = await _run_npx_skill_add(package, Path(tmpdir))
        if not ok:
            return message
        imported = await import_installed_skills(db_path, Path(tmpdir), f"npx skills add {package}")
    if not imported:
        return f"I ran npx for {package}, but I could not find any SKILL.md files to import."
    names = ", ".join(imported[:6])
    suffix = "" if len(imported) <= 6 else f", and {len(imported) - 6} more"
    return f"Imported {len(imported)} proposed skill(s) from {package}: {names}{suffix}. None are active yet."


async def import_installed_skills(db_path: str, install_root: Path, source_label: str) -> list[str]:
    skill_files = _discover_skill_files(install_root)
    names = []
    for skill_file in skill_files:
        reply = await _import_skill_file(db_path, skill_file, source_label)
        match = re.match(r"Imported (.+?) as a proposed skill", reply)
        names.append(match.group(1) if match else skill_file.parent.name)
    return names


async def _import_skill_file(db_path: str, skill_file: Path, request_text: str) -> str:
    text = skill_file.read_text("utf-8")
    name = _extract_name(text, skill_file.parent.name)
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
        db_path, skill_id, request_text, f"Imported skill: {name}",
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


async def _run_npx_skill_add(package: str, cwd: Path) -> tuple[bool, str]:
    process = await asyncio.create_subprocess_exec(
        "npx", "--yes", "skills", "add", package,
        "--all", "-y", "--copy",
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=180)
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return False, "The npx skill import timed out before any skill was registered."
    if process.returncode != 0:
        error = (stderr or stdout).decode("utf-8", errors="replace").strip()
        return False, f"The npx skill import failed: {error[:500]}"
    return True, stdout.decode("utf-8", errors="replace")


def _discover_skill_files(root: Path) -> list[Path]:
    preferred = sorted((root / ".agents" / "skills").glob("*/SKILL.md"))
    files = preferred or sorted(root.rglob("SKILL.md"))
    seen: set[Path] = set()
    unique = []
    for path in files:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique[:40]


def parse_skill_summary(path: str) -> dict[str, object]:
    text = Path(path).read_text("utf-8")
    return {
        "name": _extract_name(text, Path(path).parent.name),
        "description": _extract_description(text),
        "triggers": _extract_list(text, "trigger"),
        "tools": _extract_list(text, "tool"),
        "permissions": _permission_guess(text),
    }


def adapt_imported_skill_for_maya(scaffold_path: str, skill_name: str) -> bool:
    path = Path(scaffold_path)
    if not path.exists() or not path.is_file():
        return False
    text = path.read_text("utf-8")
    if "## Maya Activation Wrapper" in text:
        return True
    wrapper = f"""## Maya Activation Wrapper
Imported skill adapted for Maya review and activation.

## Trigger Phrases
trigger: review, critique, improve, polish, or design feedback for {skill_name}
non-trigger: booking, payment, login, secrets, private data, medical advice, legal advice, or unrelated memory changes

## Safety
hard no: no private exposure, no secret handling, no payments, no sending, no deletes, no deploys, no account actions
safe actions:
1) review visible or generated artifacts
2) suggest design improvements
3) produce critique notes
confirmation actions:
1) editing files
2) activating this skill

## Activation Tests
happy path: user asks for design critique and Maya returns practical improvements.
success: response is useful, scoped, and does not perform risky actions.
failure path: request includes secrets, payments, login, or private exposure.
rollback: refuse the risky part and keep the skill inactive if tests fail.
regression: unrelated prompts should not activate this skill.
expected: Maya keeps normal routing and safety gates.

"""
    path.write_text(wrapper + text, "utf-8")
    return True


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
