from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from maya_core.repo_paths import repo_root


ROOT = repo_root(__file__)
MANIFEST_PATH = ROOT / "dependency_manifest.json"


@dataclass(frozen=True)
class DependencyStatus:
    id: str
    category: str
    requirement: str
    purpose: str
    status: str
    detail: str


def load_dependency_manifest(path: Path | str = MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dependency_statuses(path: Path | str = MANIFEST_PATH) -> list[DependencyStatus]:
    load_dotenv(ROOT / ".env")
    items = load_dependency_manifest(path).get("items", [])
    return [_check_item(dict(item)) for item in items]


def dependency_readiness_text(path: Path | str = MANIFEST_PATH) -> str:
    statuses = dependency_statuses(path)
    lines = ["Dependency readiness:"]
    for index, status in enumerate(statuses, start=1):
        lines.append(
            f"{index}) {status.id}: {status.status} | {status.requirement} | "
            f"{status.category} | {status.detail}"
        )
    return "\n".join(lines)


def readiness_summary(path: Path | str = MANIFEST_PATH) -> dict[str, int]:
    counts = {"ready": 0, "missing": 0, "unknown": 0}
    for status in dependency_statuses(path):
        counts[status.status] = counts.get(status.status, 0) + 1
    return counts


def _check_item(item: dict[str, Any]) -> DependencyStatus:
    status, detail = _status_detail(item)
    return DependencyStatus(
        id=str(item.get("id", "")),
        category=str(item.get("category", "")),
        requirement=str(item.get("requirement", "")),
        purpose=str(item.get("purpose", "")),
        status=status,
        detail=detail,
    )


def _status_detail(item: dict[str, Any]) -> tuple[str, str]:
    if item.get("import"):
        module = str(item["import"])
        return ("ready", module) if importlib.util.find_spec(module) else ("missing", module)
    if item.get("binary"):
        binary = str(item["binary"])
        found = shutil.which(binary)
        if found:
            if item.get("special_check") == "codex_chatgpt_auth":
                return _codex_auth_detail(found)
            return "ready", found
        alternate = item.get("alternate_path")
        if alternate and Path(str(alternate)).exists():
            return "ready", str(alternate)
        return "missing", binary
    if item.get("env"):
        env = str(item["env"])
        return ("ready", env) if os.getenv(env) else ("missing", env)
    if item.get("path"):
        raw = str(item["path"])
        path = Path(raw).expanduser()
        return ("ready", str(path)) if path.exists() else ("missing", raw)
    return "unknown", "manual check required"


def _codex_auth_detail(found: str) -> tuple[str, str]:
    try:
        proc = subprocess.run(
            ["codex", "login", "status"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:
        return "unknown", f"{found}; auth check failed: {exc}"
    output = f"{proc.stdout}\n{proc.stderr}".lower()
    if "logged in using chatgpt" in output:
        return "ready", "codex logged in using ChatGPT"
    if "logged in" in output:
        return "unknown", "codex logged in, auth type not confirmed as ChatGPT"
    return "missing", "codex installed but not confirmed logged in"


if __name__ == "__main__":
    print(dependency_readiness_text())
