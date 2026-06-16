from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import json
import tempfile
from pathlib import Path

from maya_core.dependency_manifest import dependency_readiness_text, dependency_statuses, readiness_summary


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="maya-deps-") as tmp:
        manifest = Path(tmp) / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "version": 1,
                    "items": [
                        {"id": "python.json", "category": "python", "requirement": "required", "import": "json", "purpose": "test"},
                        {"id": "env.missing", "category": "provider_key", "requirement": "optional", "env": "MAYA_NO_SUCH_ENV", "purpose": "test"},
                        {"id": "manual.test", "category": "macos_permission", "requirement": "manual", "purpose": "test"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        statuses = dependency_statuses(manifest)
        by_id = {status.id: status for status in statuses}
        _require(by_id["python.json"].status == "ready", "python import check failed")
        _require(by_id["env.missing"].status == "missing", "env missing check failed")
        _require(by_id["manual.test"].status == "unknown", "manual check should be unknown")
        summary = readiness_summary(manifest)
        _require(summary["ready"] == 1 and summary["missing"] == 1 and summary["unknown"] == 1, "summary wrong")
        text = dependency_readiness_text(manifest)
        _require("Dependency readiness:" in text and "python.json" in text, "readiness text wrong")
    print("dependency_manifest_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
