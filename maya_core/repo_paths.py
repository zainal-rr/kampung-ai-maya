from __future__ import annotations

from pathlib import Path


def repo_root(anchor: str | Path | None = None) -> Path:
    start = Path(anchor).resolve() if anchor is not None else Path(__file__).resolve()
    for parent in (start.parent, *start.parents):
        if (parent / "local_ci.py").exists() and (parent / ".git").exists():
            return parent
    return start.parent
