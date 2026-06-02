from __future__ import annotations

import os
from pathlib import Path


DEFAULT_WORKSPACE_ROOT = Path.home() / "Desktop" / "Maya"
LEGACY_WORKSPACE_ROOT = Path.home() / "Downloads" / "Kampung AI"
WORKSPACE_DIRS = (
    "documents",
    "notes",
    "presentations",
    "spreadsheets",
    "drawings",
    "Projects",
    "artifacts",
    "screenshots",
    "reports",
    "inbox",
    "voice_sessions",
)


def maya_workspace_root() -> Path:
    return Path(os.getenv("MAYA_WORKSPACE_ROOT", str(DEFAULT_WORKSPACE_ROOT))).expanduser()


def legacy_workspace_root() -> Path:
    return LEGACY_WORKSPACE_ROOT


def workspace_dir(name: str, *, create: bool = False) -> Path:
    root = maya_workspace_root()
    path = root / name
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_workspace_tree() -> Path:
    root = maya_workspace_root()
    for name in WORKSPACE_DIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def project_roots() -> tuple[Path, ...]:
    roots = [
        Path.home() / "projects",
        workspace_dir("Projects"),
        legacy_workspace_root() / "Projects",
    ]
    raw = os.getenv("MAYA_PROJECT_ROOTS", "")
    roots.extend(Path(item.strip()).expanduser() for item in raw.split(",") if item.strip())
    return tuple(dict.fromkeys(path.resolve(strict=False) for path in roots))


def is_workspace_path(path: Path) -> bool:
    resolved = path.expanduser().resolve(strict=False)
    roots = (maya_workspace_root(), legacy_workspace_root())
    return any(_within(resolved, root) for root in roots)


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.expanduser().resolve(strict=False))
        return True
    except ValueError:
        return False
