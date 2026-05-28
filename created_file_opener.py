from __future__ import annotations

from pathlib import Path

from utils import OSBridge


def app_candidates_for_path(path: Path) -> tuple[str | None, ...]:
    suffix = path.suffix.lower()
    if suffix == ".md":
        return ("Cursor", "TextEdit", None)
    if suffix == ".docx":
        return ("Microsoft Word",)
    if suffix == ".xlsx":
        return ("Microsoft Excel",)
    if suffix == ".pptx":
        return ("Microsoft PowerPoint",)
    if suffix == ".html":
        return ("Google Chrome",)
    return (None,)


def open_created_file(path: Path, bridge: OSBridge | None = None, app_name: str | None = None) -> str | None:
    bridge = bridge or OSBridge()
    candidates = (app_name,) if app_name else app_candidates_for_path(path)
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            bridge.open_file(str(path), candidate)
            return candidate
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    return None
