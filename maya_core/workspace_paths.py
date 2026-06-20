from __future__ import annotations

from pathlib import Path

from maya_core.maya_runtime_config import runtime_config

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
    return runtime_config().workspace_root


def legacy_workspace_root() -> Path:
    return runtime_config().legacy_workspace_root


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
    return runtime_config().project_roots


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
