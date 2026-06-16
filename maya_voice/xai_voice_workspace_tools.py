from __future__ import annotations

from pathlib import Path

from maya_core.workspace_paths import maya_workspace_root


def read_desktop_maya_workspace(question: str) -> str:
    root = maya_workspace_root()
    lines = [f"Desktop Maya workspace: {root}"]
    if not root.exists():
        return "\n".join(lines + ["Workspace folder does not exist yet."])
    lines.append("Folders:")
    for folder in _workspace_folders(root):
        count = len([item for item in folder.iterdir()]) if folder.exists() else 0
        lines.append(f"{folder.name}: {count} items")
    files = _workspace_matches(root, question)
    if files:
        lines.append("Relevant recent files:")
        for index, path in enumerate(files[:12], start=1):
            lines.append(f"{index}) {path.relative_to(root)}")
        excerpt = _safe_workspace_excerpt(files[0])
        if excerpt:
            lines.append(f"\nExcerpt from {files[0].name}:\n{excerpt}")
    return "\n".join(lines)[:5000]


def _workspace_folders(root: Path) -> list[Path]:
    names = (
        "documents", "notes", "presentations", "spreadsheets", "drawings",
        "Projects", "artifacts", "screenshots", "reports", "inbox",
    )
    return [root / name for name in names]


def _workspace_matches(root: Path, question: str) -> list[Path]:
    tokens = {token for token in question.lower().replace("-", " ").split() if len(token) > 3}
    files = [path for path in root.rglob("*") if path.is_file() and not path.name.startswith(".")]
    if tokens:
        scored = [(sum(token in str(path).lower() for token in tokens), path) for path in files]
        files = [path for score, path in scored if score > 0]
    return sorted(files, key=lambda path: path.stat().st_mtime, reverse=True)[:20]


def _safe_workspace_excerpt(path: Path) -> str:
    if path.suffix.lower() not in {".md", ".txt", ".csv"}:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore").strip()[:1200]
    except OSError:
        return ""
