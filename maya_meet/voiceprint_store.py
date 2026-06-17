from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from maya_core.provenance import can_authorize_confirmation
from maya_meet.models import VOICEPRINT_STATUSES


VOICEPRINT_ROOT = Path.home() / "Desktop" / "Maya" / "voiceprints"
ACTIVE_FILE = "owner_voiceprint.json"


@dataclass(frozen=True)
class EnrollmentResult:
    status: str
    reason_code: str
    enrollment_id: str = ""

    def as_dict(self) -> dict[str, str]:
        return {"status": self.status, "reason_code": self.reason_code, "enrollment_id": self.enrollment_id}


def active_voiceprint_path(root: Path | None = None) -> Path:
    return (root or VOICEPRINT_ROOT).expanduser() / ACTIVE_FILE


def load_voiceprint(root: Path | None = None) -> dict[str, Any]:
    path = active_voiceprint_path(root)
    if not path.exists():
        return {"status": "not_enrolled"}
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "revoked", "reason_code": "voiceprint_store_unreadable"}


def enroll_voiceprint(
    *,
    owner_provenance,
    embedding: list[float],
    threshold: float,
    sample_count: int,
    root: Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> EnrollmentResult:
    if not can_authorize_confirmation(owner_provenance):
        return EnrollmentResult("rejected", "unauthorized_enrollment_source")
    if sample_count <= 0 or not embedding:
        return EnrollmentResult("rejected", "missing_voiceprint_samples")
    enrollment_id = "vp_" + uuid.uuid4().hex[:16]
    payload = {
        "status": "enrolled",
        "enrollment_id": enrollment_id,
        "embedding": [float(value) for value in embedding],
        "threshold": float(threshold),
        "sample_count": int(sample_count),
        "created_at": time.time(),
        "updated_at": time.time(),
        "storage_protection": "file_0600_personal_data_root",
        "metadata": dict(metadata or {}),
    }
    _write_payload(payload, root)
    return EnrollmentResult("enrolled", "owner_channel_authenticated", enrollment_id)


def revoke_voiceprint(*, owner_provenance, root: Path | None = None) -> EnrollmentResult:
    if not can_authorize_confirmation(owner_provenance):
        return EnrollmentResult("rejected", "unauthorized_enrollment_source")
    current = load_voiceprint(root)
    payload = {
        "status": "revoked",
        "enrollment_id": str(current.get("enrollment_id") or ""),
        "revoked_at": time.time(),
        "updated_at": time.time(),
        "storage_protection": "file_0600_personal_data_root",
    }
    _write_payload(payload, root)
    return EnrollmentResult("revoked", "owner_channel_authenticated", payload["enrollment_id"])


def enrollment_status(root: Path | None = None) -> str:
    status = str(load_voiceprint(root).get("status") or "not_enrolled")
    return status if status in VOICEPRINT_STATUSES else "revoked"


def _write_payload(payload: dict[str, Any], root: Path | None) -> None:
    path = active_voiceprint_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True, indent=2), "utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)
    os.chmod(path, 0o600)
