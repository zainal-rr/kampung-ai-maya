from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class HarnessArtifact:
    kind: str
    path: str = ""
    url: str = ""
    summary: str = ""
    source_tool: str = ""
    exists_status: str = "unknown"
    delivery_status: str = "local"
    checksum: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "path": self.path,
            "url": self.url,
            "summary": self.summary,
            "source_tool": self.source_tool,
            "exists_status": self.exists_status,
            "delivery_status": self.delivery_status,
            "checksum": self.checksum,
        }


@dataclass(frozen=True)
class GroundedObservation:
    source: str
    frontmost_app: str = ""
    running_apps: tuple[str, ...] = ()
    page_title: str = ""
    url: str = ""
    text_summary: str = ""
    text_hash: str = ""
    modal_state: str = ""
    clickable_targets: tuple[str, ...] = ()
    fillable_targets: tuple[str, ...] = ()
    screenshot_status: str = ""
    screen_summary: str = ""
    confidence: float = 0.0
    provenance: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "frontmost_app": self.frontmost_app,
            "running_apps": list(self.running_apps),
            "page_title": self.page_title,
            "url": self.url,
            "text_summary": self.text_summary,
            "text_hash": self.text_hash,
            "modal_state": self.modal_state,
            "clickable_targets": list(self.clickable_targets),
            "fillable_targets": list(self.fillable_targets),
            "screenshot_status": self.screenshot_status,
            "screen_summary": self.screen_summary,
            "confidence": self.confidence,
            "provenance": list(self.provenance),
        }


def local_artifact(kind: str, path: str, summary: str, source_tool: str) -> HarnessArtifact:
    local_path = Path(path).expanduser()
    return HarnessArtifact(
        kind=kind,
        path=str(local_path),
        summary=summary,
        source_tool=source_tool,
        exists_status="exists" if local_path.exists() else "unavailable",
        checksum=_small_checksum(local_path),
    )


def _small_checksum(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        digest.update(handle.read(1024 * 1024))
    return digest.hexdigest()[:16]
