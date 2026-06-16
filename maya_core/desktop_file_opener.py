from __future__ import annotations

import re
from pathlib import Path

from workspace_paths import legacy_workspace_root, maya_workspace_root, workspace_dir
from utils import OSBridge


TYPE_CONFIG = {
    "word": ((".docx",), ("documents",), "Microsoft Word"),
    "docx": ((".docx",), ("documents",), "Microsoft Word"),
    "powerpoint": ((".pptx",), ("presentations",), "Microsoft PowerPoint"),
    "presentation": ((".pptx",), ("presentations",), "Microsoft PowerPoint"),
    "pptx": ((".pptx",), ("presentations",), "Microsoft PowerPoint"),
    "excel": ((".xlsx",), ("spreadsheets",), "Microsoft Excel"),
    "spreadsheet": ((".xlsx",), ("spreadsheets",), "Microsoft Excel"),
    "xlsx": ((".xlsx",), ("spreadsheets",), "Microsoft Excel"),
    "markdown": ((".md",), ("notes",), ("Cursor", "TextEdit")),
    "md": ((".md",), ("notes",), ("Cursor", "TextEdit")),
}

ALL_SUFFIXES = (".md", ".docx", ".pptx", ".xlsx")


class DesktopFileOpener:
    def __init__(self, bridge: OSBridge | None = None):
        self.bridge = bridge or OSBridge()

    async def handle(self, text: str, channel: str) -> str | None:
        request = _parse_request(text)
        if request is None:
            return None
        kind, query = request
        path, app, options = self._resolve(kind, query)
        if path is None:
            if options:
                return "I found more than one matching file:\n" + "\n".join(
                    f"{idx}) {item}" for idx, item in enumerate(options[:5], start=1)
                )
            return "I could not find that file in Desktop Maya."
        if channel == "telegram":
            return f"File found: {path}\n[file:{path}]"
        try:
            opened_app = self._open_file(path, app)
        except Exception as exc:
            return f"I found the file at {path}, but I could not open it: {exc}"
        suffix = f" in {opened_app}" if opened_app else ""
        return f"I opened {path.name}{suffix}."

    def _resolve(self, kind: str, query: str) -> tuple[Path | None, str | tuple[str, ...] | None, list[Path]]:
        suffixes, folders, app = _type_details(kind)
        candidates = _candidate_files(suffixes, folders)
        if not candidates:
            return None, app, []
        if not query:
            return candidates[0], app, []
        matches = _rank_matches(candidates, query)
        if len(matches) == 1:
            return matches[0], app, []
        if len(matches) > 1 and _ambiguous(matches):
            return None, app, matches
        return (matches[0], app, []) if matches else (None, app, [])

    def _open_file(self, path: Path, app: str | tuple[str, ...] | None) -> str | None:
        if not isinstance(app, tuple):
            self.bridge.open_file(str(path), app)
            return app
        last_error: Exception | None = None
        for candidate in app:
            try:
                self.bridge.open_file(str(path), candidate)
                return candidate
            except Exception as exc:
                last_error = exc
        if last_error:
            raise last_error
        self.bridge.open_file(str(path), None)
        return None


def _parse_request(text: str) -> tuple[str, str] | None:
    cleaned = " ".join(text.strip().split())
    lowered = cleaned.lower()
    if lowered in {"open latest file", "open the last file", "show me the latest file", "open latest artifact"}:
        return "file", ""
    latest = re.match(r"^(?:open|show(?: me)?)\s+(?:the\s+)?latest\s+(.+?)(?:\s+file)?$", lowered)
    if latest:
        kind = _kind_from_text(latest.group(1))
        return (kind, "") if kind else None
    named = re.match(r"^(?:open|show(?: me)?)\s+(.+)$", cleaned, re.I)
    if not named:
        return None
    body = named.group(1).strip()
    kind = _kind_from_text(body)
    if not kind:
        return None
    query = _strip_kind_words(body)
    return kind, query


def _kind_from_text(text: str) -> str:
    lowered = text.lower()
    for key in TYPE_CONFIG:
        if re.search(rf"\b{re.escape(key)}\b", lowered):
            return key
    if lowered.endswith(".md"):
        return "md"
    if lowered.endswith(".docx"):
        return "docx"
    if lowered.endswith(".pptx"):
        return "pptx"
    if lowered.endswith(".xlsx"):
        return "xlsx"
    return ""


def _strip_kind_words(text: str) -> str:
    cleaned = re.sub(
        r"\b(word|docx|document|powerpoint|presentation|pptx|excel|spreadsheet|xlsx|markdown|md|file)\b",
        " ",
        text,
        flags=re.I,
    )
    return " ".join(cleaned.replace(".", " ").split())


def _type_details(kind: str) -> tuple[tuple[str, ...], tuple[str, ...], str | tuple[str, ...] | None]:
    if kind == "file":
        return ALL_SUFFIXES, ("notes", "documents", "presentations", "spreadsheets"), None
    suffixes, folders, app = TYPE_CONFIG.get(kind, (ALL_SUFFIXES, ("",), None))
    return suffixes, folders, app


def _candidate_files(suffixes: tuple[str, ...], folders: tuple[str, ...]) -> list[Path]:
    roots: list[Path] = []
    for folder in folders:
        roots.append(workspace_dir(folder) if folder else maya_workspace_root())
        roots.append(legacy_workspace_root() / folder if folder else legacy_workspace_root())
    files: list[Path] = []
    for root in dict.fromkeys(roots):
        if not root.exists():
            continue
        for suffix in suffixes:
            files.extend(path for path in root.rglob(f"*{suffix}") if path.is_file())
    files.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return files


def _rank_matches(candidates: list[Path], query: str) -> list[Path]:
    needle = _slug(query)
    scored = []
    for path in candidates:
        hay = _slug(path.stem)
        if needle == hay:
            scored.append((3, path))
        elif needle and needle in hay:
            scored.append((2, path))
        elif all(token in hay for token in needle.split("-") if token):
            scored.append((1, path))
    scored.sort(key=lambda item: (item[0], item[1].stat().st_mtime), reverse=True)
    return [path for _, path in scored]


def _ambiguous(paths: list[Path]) -> bool:
    if len(paths) <= 1:
        return False
    return paths[0].stem.lower() != paths[1].stem.lower()


def _slug(text: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", text.lower()))
