from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


"""Guardrail against reintroducing the retired implementation architecture."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent
SKIP_DIRS = {"logs", "__pycache__", ".git", "htmlcov", "venv", ".venv", ".mypy_cache", ".pytest_cache"}
FORBIDDEN = (
    "Kimi",
    "kimi",
    "Moonshot",
    "moonshot",
    "KIMI",
    "MOONSHOT",
    "TheHands",
    "orchestrator.py",
    "from orchestrator import",
    "Orchestrator(",
    "ARTISAN_ENGINE",
)


def main() -> None:
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if path.name == Path(__file__).name:
            continue
        if not path.is_file() or _skip(path):
            continue
        try:
            text = path.read_text("utf-8")
        except UnicodeDecodeError:
            continue
        for marker in FORBIDDEN:
            if marker in text:
                hits.append(f"{path.relative_to(ROOT)}: {marker}")
    if hits:
        raise AssertionError("Retired architecture markers found:\n" + "\n".join(hits[:40]))
    print("legacy_architecture_removed_smoke: ok")


def _skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)


if __name__ == "__main__":
    main()
