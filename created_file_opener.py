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
            if candidate == "Microsoft Word":
                _focus_word_document(bridge, path)
            return candidate
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    return None


def _focus_word_document(bridge: OSBridge, path: Path) -> None:
    if not hasattr(bridge, "_run_applescript"):
        return
    safe_path = str(path).replace("\\", "\\\\").replace('"', '\\"')
    result = bridge._run_applescript(
        'set targetPath to "' + safe_path + '"\n'
        'set refreshState to "opened"\n'
        'tell application "Microsoft Word"\n'
        "activate\n"
        "repeat with d in documents\n"
        'set docPath to ""\n'
        "try\n"
        "set docPath to POSIX path of (full name of d as alias)\n"
        "end try\n"
        "if docPath is targetPath then\n"
        "if saved of d is false then\n"
        'set refreshState to "unsaved_open_copy"\n'
        "else\n"
        "close d saving no\n"
        "end if\n"
        "exit repeat\n"
        "end if\n"
        "end repeat\n"
        'if refreshState is not "unsaved_open_copy" then open POSIX file targetPath\n'
        'set activePath to ""\n'
        'try\n'
        'set activePath to POSIX path of (full name of active document as alias)\n'
        'end try\n'
        'if refreshState is not "unsaved_open_copy" and activePath is not targetPath then set refreshState to "open_not_verified"\n'
        "end tell\n"
        "return refreshState"
    )
    state = str(result).strip()
    if state == "unsaved_open_copy":
        raise RuntimeError(
            "Word already has this document open with unsaved changes, so I did not reload the file from disk."
        )
    if state == "open_not_verified":
        raise RuntimeError("Word did not verify the updated document as the active open file.")
