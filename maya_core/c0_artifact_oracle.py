from __future__ import annotations

import re
from html import unescape
from pathlib import Path
from typing import Any
from zipfile import ZipFile

PathPattern = re.compile(r"(/[^\s\]]+\.(?:md|txt|docx|xlsx|pptx|html))")


def artifact_oracle_status(task: Any, payload: dict[str, Any]) -> str:
    paths = _artifact_paths(payload)
    if not paths:
        return ""
    prompt = str(getattr(task, "prompt", "") or "")
    if _expects_directory_artifact(prompt):
        return _directory_artifact_status(prompt, paths)
    expected_suffix = _expected_artifact_suffix(prompt)
    for path in paths:
        if not path.exists():
            continue
        if expected_suffix and path.suffix.lower() != expected_suffix:
            continue
        text = _artifact_text(path)
        if _artifact_content_matches(prompt, text, path):
            return "ok"
        return "content_too_thin_or_mismatched"
    existing = [path for path in paths if path.exists()]
    if existing:
        return "wrong_kind_or_path"
    return ""


def _artifact_paths(payload: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for artifact in payload.get("artifacts") or ():
        path = str(artifact.get("path") or "")
        if path:
            paths.append(Path(path).expanduser())
    for match in PathPattern.findall(str(payload["state"].get("final_response") or "")):
        candidate = Path(match).expanduser()
        if candidate not in paths:
            paths.append(candidate)
    return paths


def _expects_directory_artifact(prompt: str) -> bool:
    lowered = prompt.lower()
    return "create a folder" in lowered or "create a project" in lowered


def _directory_artifact_status(prompt: str, paths: list[Path]) -> str:
    for path in paths:
        if not path.exists():
            continue
        if not path.is_dir():
            return "wrong_kind_file_instead_of_directory"
        if _directory_artifact_matches(prompt, path):
            return "ok"
        return "wrong_path_or_name"
    return ""


def _directory_artifact_matches(prompt: str, path: Path) -> bool:
    expected = _expected_directory_name(prompt)
    if expected:
        expected_key = _directory_key(expected)
        haystack = _directory_key(f"{path.name} {path}")
        return bool(expected_key and expected_key in haystack)
    tokens = _artifact_prompt_tokens(prompt)
    if not tokens:
        return True
    haystack = f"{path.name} {path}".lower().replace("-", "").replace("_", "")
    hits = sum(1 for token in tokens if token in haystack)
    return hits >= min(len(tokens), 2)


def _expected_directory_name(prompt: str) -> str:
    lowered = str(prompt or "").lower()
    for pattern in (
        r"\b(?:folder|directory|project)\s+(?:called|named|for)\s+([a-z0-9][a-z0-9 _-]{1,80})",
    ):
        match = re.search(pattern, lowered)
        if match:
            return match.group(1).strip()
    return ""


def _directory_key(value: str) -> str:
    return "".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _expected_artifact_suffix(prompt: str) -> str:
    lowered = prompt.lower()
    if "spreadsheet" in lowered or "xlsx" in lowered:
        return ".xlsx"
    if "word document" in lowered or "local document" in lowered or "docx" in lowered:
        return ".docx"
    if "markdown" in lowered:
        return ".md"
    match = re.search(r"\b[\w./ -]+(\.(?:txt|md|docx|xlsx|html))\b", prompt, flags=re.I)
    return match.group(1).lower() if match else ""


def _artifact_text(path: Path) -> str:
    try:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md", ".html"}:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".docx":
            return _docx_text(path)
        if suffix == ".xlsx":
            return _xlsx_text(path)
    except Exception:  # noqa: BLE001 - a broken artifact is not content-valid.
        return ""
    return ""


def _docx_text(path: Path) -> str:
    with ZipFile(path) as doc:
        xml = doc.read("word/document.xml").decode("utf-8", errors="ignore")
    return _xml_text(xml)


def _xlsx_text(path: Path) -> str:
    parts: list[str] = []
    with ZipFile(path) as book:
        for name in book.namelist():
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                parts.append(_xml_text(book.read(name).decode("utf-8", errors="ignore")))
            elif name == "xl/sharedStrings.xml":
                parts.append(_xml_text(book.read(name).decode("utf-8", errors="ignore")))
    return "\n".join(parts)


def _xml_text(xml: str) -> str:
    text = re.sub(r"<[^>]+>", " ", xml)
    return " ".join(unescape(text).split())


def _artifact_content_matches(prompt: str, text: str, path: Path) -> bool:
    normalized = " ".join(str(text or "").split())
    if len(normalized) < _minimum_artifact_text_length(path):
        return False
    tokens = _artifact_prompt_tokens(prompt)
    if not tokens:
        return True
    haystack = normalized.lower().replace("-", "")
    hits = sum(1 for token in tokens if token in haystack)
    required = min(len(tokens), 3)
    return hits >= required


def _minimum_artifact_text_length(path: Path) -> int:
    if path.suffix.lower() == ".xlsx":
        return 20
    if path.suffix.lower() in {".txt", ".md"}:
        return 35
    return 80


def _artifact_prompt_tokens(prompt: str) -> list[str]:
    tokens = []
    for token in re.findall(r"[a-z0-9][a-z0-9-]{2,}", prompt.lower()):
        if token in _ARTIFACT_STOP_TOKENS:
            continue
        normalized = token.replace("-", "")
        if normalized and normalized not in tokens:
            tokens.append(normalized)
    return tokens[:8]


_ARTIFACT_STOP_TOKENS = {
    "about", "called", "columns", "concise", "create", "document", "exactly", "external",
    "file", "folder", "local", "markdown", "named", "note", "notes", "project", "short",
    "simple", "spreadsheet", "three", "titled", "with", "word", "xlsx",
}
