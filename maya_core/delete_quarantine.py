from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from maya_core.workspace_paths import maya_workspace_root


@dataclass(frozen=True)
class QuarantineRecord:
    original_path: str
    quarantined_path: str
    reason: str
    created_at: str


def quarantine_user_file(path: Path, *, reason: str = "user_requested_delete") -> QuarantineRecord:
    source = Path(path).expanduser()
    source_resolved = source.resolve(strict=False)
    if not source.exists() and not source.is_symlink():
        raise FileNotFoundError(str(source_resolved))
    if not source.is_symlink() and not source.is_file():
        raise FileNotFoundError(str(source_resolved))
    trash = maya_workspace_root() / ".trash" / datetime.now(UTC).strftime("%Y%m%d")
    trash.mkdir(parents=True, exist_ok=True)
    target = _unique_target(trash / source.name)
    shutil.move(str(source), str(target))
    record = QuarantineRecord(
        original_path=str(source.expanduser().resolve(strict=False)),
        quarantined_path=str(target),
        reason=reason,
        created_at=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    target.with_suffix(target.suffix + ".restore.json").write_text(json.dumps(asdict(record), indent=2), "utf-8")
    return record


def _unique_target(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Could not allocate quarantine path for {path}")
