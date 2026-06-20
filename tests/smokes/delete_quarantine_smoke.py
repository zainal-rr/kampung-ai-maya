from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import json
import os
import tempfile
from pathlib import Path

from maya_core.delete_quarantine import quarantine_user_file


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-delete-quarantine-") as tmp:
        workspace = Path(tmp) / "Maya"
        os.environ["MAYA_WORKSPACE_ROOT"] = str(workspace)
        source = Path(tmp) / "user-note.txt"
        source.write_text("do not hard delete me", "utf-8")
        record = quarantine_user_file(source, reason="smoke_test")
        quarantined = Path(record.quarantined_path)
        metadata = quarantined.with_suffix(quarantined.suffix + ".restore.json")
        _require(not source.exists(), "source file was not moved")
        _require(quarantined.exists(), "quarantined file missing")
        _require(metadata.exists(), "restore metadata missing")
        payload = json.loads(metadata.read_text("utf-8"))
        _require(payload["original_path"] == str(source.resolve(strict=False)), "original path not recorded")
        _require(payload["reason"] == "smoke_test", "reason not recorded")
        symlink_target = Path(tmp) / "target.txt"
        symlink_target.write_text("keep target", "utf-8")
        symlink = Path(tmp) / "link.txt"
        symlink.symlink_to(symlink_target)
        symlink_record = quarantine_user_file(symlink, reason="symlink_test")
        quarantined_link = Path(symlink_record.quarantined_path)
        _require(not symlink.exists() and symlink.is_symlink() is False, "source symlink was not removed")
        _require(symlink_target.exists(), "symlink target was moved instead of symlink")
        _require(quarantined_link.is_symlink(), "quarantined symlink is not a symlink")
        _require(quarantined_link.resolve(strict=True) == symlink_target.resolve(strict=True), "symlink target changed")
        payload = json.loads(quarantined_link.with_suffix(quarantined_link.suffix + ".restore.json").read_text("utf-8"))
        _require(payload["original_path"] == str(symlink.resolve(strict=False)), "symlink original path not recorded")
    print("delete_quarantine_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
