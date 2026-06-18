from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import tempfile
from pathlib import Path
from unittest.mock import patch

from maya_core.provenance import make_provenance
from maya_meet import voiceprint_live
from maya_meet.voiceprint_store import enroll_voiceprint


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    accepted = voiceprint_live._acceptance([0.91, 0.93], [0.2, 0.3], [0.4], 0.86)
    _require(accepted["m2_enable_recommended"], str(accepted))
    rejected_owner = voiceprint_live._acceptance([0.80, 0.93], [0.2], [0.4], 0.86)
    _require("owner_false_reject" in rejected_owner["blockers"], str(rejected_owner))
    rejected_negative = voiceprint_live._acceptance([0.91], [0.9], [0.4], 0.86)
    _require("negative_false_accept" in rejected_negative["blockers"], str(rejected_negative))
    rejected_replay = voiceprint_live._acceptance([0.91], [0.2], [0.9], 0.86)
    _require("recording_replay_accept" in rejected_replay["blockers"], str(rejected_replay))
    missing = voiceprint_live._acceptance([0.91], [], [], 0.86)
    _require("negative_samples_missing" in missing["blockers"], str(missing))
    _require("recording_replay_missing" in missing["blockers"], str(missing))

    with tempfile.TemporaryDirectory(prefix="maya-vp-live-") as tmp:
        root = Path(tmp)
        result = enroll_voiceprint(
            owner_provenance=make_provenance("owner_voice"),
            embedding=[1.0, 0.0, 0.0],
            threshold=0.86,
            sample_count=3,
            root=root,
            metadata={"model": "test"},
        )
        _require(result.status == "enrolled", str(result))
        with patch("maya_meet.voiceprint_store.VOICEPRINT_ROOT", root), patch("maya_meet.voiceprint_live.load_voiceprint") as load:
            load.return_value = {
                "status": "enrolled",
                "enrollment_id": result.enrollment_id,
                "embedding": [1.0, 0.0, 0.0],
                "threshold": 0.86,
                "sample_count": 3,
                "created_at": 123.0,
                "metadata": {"model": "test"},
            }
            status = voiceprint_live._safe_status()
        _require(status["status"] == "enrolled", str(status))
        _require("embedding" not in str(status).lower(), "status leaked embedding")
    print("meet_voiceprint_live_smoke: ok")


if __name__ == "__main__":
    main()
