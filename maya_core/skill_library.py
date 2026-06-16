from __future__ import annotations

import shutil
from pathlib import Path


LIBRARY_DIRS = ("active", "proposed", "disabled", "research_notes", "tests")


def skill_root(root: Path | None = None) -> Path:
    return root or Path("maya_skills")


def ensure_skill_library(root: Path | None = None) -> Path:
    base = skill_root(root)
    for name in LIBRARY_DIRS:
        (base / name).mkdir(parents=True, exist_ok=True)
    return base


def proposed_path(skill_id: str, root: Path | None = None) -> Path:
    base = ensure_skill_library(root)
    return base / "proposed" / f"{skill_id}.md"


def test_path(skill_id: str, root: Path | None = None) -> Path:
    base = ensure_skill_library(root)
    return base / "tests" / f"{skill_id}.md"


def mirror_skill(scaffold_path: str, status: str, root: Path | None = None) -> Path | None:
    if status not in {"active", "disabled", "proposed"}:
        return None
    if not scaffold_path:
        return None
    source = Path(scaffold_path)
    if not source.exists() or not source.is_file():
        return None
    base = ensure_skill_library(root or _root_from_source(source))
    destination = base / status / source.name
    if source.resolve() != destination.resolve():
        _copy_with_status(source, destination, status)
    return destination


def _root_from_source(source: Path) -> Path | None:
    if source.parent.name in LIBRARY_DIRS:
        return source.parent.parent
    return None


def _copy_with_status(source: Path, destination: Path, status: str) -> None:
    try:
        text = source.read_text("utf-8")
    except UnicodeDecodeError:
        shutil.copyfile(source, destination)
        return
    label = "Active" if status == "active" else "Disabled" if status == "disabled" else "Proposed"
    text = text.replace(
        "Proposed scaffold created by Maya. Human review required before activation.",
        f"{label} library mirror. Database status is source of truth.",
    )
    if f"{label} library mirror" not in text:
        text = text.replace("\n## Trigger Phrases", f"\n## Library Status\n{label} library mirror. Database status is source of truth.\n\n## Trigger Phrases", 1)
    destination.write_text(text, "utf-8")
