from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArtisanTarget:
    workflow_type: str
    cwd: Path
    permission_mode: str
    approval_state: str
    project_slug: str = ""
    original_repo_path: Path | None = None
    isolation_mode: str = "workspace"
    base_ref: str = ""
    dirty_summary: str = ""
