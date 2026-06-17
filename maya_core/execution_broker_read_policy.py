from __future__ import annotations

import re
from contextlib import suppress
from pathlib import Path
from typing import Sequence


READ_POLICIES = {"credential_deny", "jailed_roots"}
JAILED_DEFAULT_PROFILES = {
    "readonly",
    "workspace_write",
    "generated_blender",
    "browser_headless",
    "network_diagnostic",
    "screen_capture",
}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def validate_read_policy(read_policy: str) -> None:
    if read_policy not in READ_POLICIES:
        raise ValueError(f"unknown read policy: {read_policy}")


def effective_read_policy(profile: str, read_policy: str) -> str:
    if read_policy != "credential_deny":
        return read_policy
    if profile in JAILED_DEFAULT_PROFILES:
        return "jailed_roots"
    return read_policy


def personal_data_read_denies(personal_read_roots: Sequence[Path]) -> tuple[Path, ...]:
    allowed = _resolved_roots(personal_read_roots)
    protected = _protected_personal_roots()
    return tuple(path for path in protected if not any(_path_within(path, root) for root in allowed))


def path_deny_regex(path: Path) -> str:
    return re.escape(str(path)) + r"(/.*)?$"


def _protected_personal_roots() -> tuple[Path, ...]:
    home = Path.home()
    project_candidates = {PROJECT_ROOT, Path.cwd()}
    roots: list[Path] = []
    for root in project_candidates:
        roots.extend(
            [
                root / "session_history.db",
                root / "logs",
                root / "backups",
            ]
        )
    desktop_maya = home / "Desktop" / "Maya"
    roots.extend(
        desktop_maya / name
        for name in (
            "documents",
            "spreadsheets",
            "presentations",
            "artifacts",
            "voice_sessions",
            "screenshots",
            "reports",
            "notes",
        )
    )
    roots.extend(home / name for name in ("Documents", "Downloads", "Pictures", "Movies", "Music"))
    with suppress(OSError):
        roots.extend(path for path in home.glob("*") if path.is_file())
    return _dedupe_paths(_resolved_roots(tuple(roots)))


def _resolved_roots(roots: Sequence[Path | None]) -> tuple[Path, ...]:
    resolved: list[Path] = []
    for root in roots:
        if root is None:
            continue
        try:
            resolved.append(Path(root).expanduser().resolve(strict=False))
        except OSError:
            continue
    return tuple(resolved)


def _path_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return path == root


def _dedupe_paths(paths: Sequence[Path]) -> tuple[Path, ...]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        text = str(path)
        if text in seen:
            continue
        seen.add(text)
        result.append(path)
    return tuple(result)
