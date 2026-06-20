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

from maya_core.demo_evidence import EXPECTED_DEMOS, refresh_latest_demo_evidence, validate_latest_demo_evidence, write_latest_demo_files


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / "logs" / "demos"
        log_dir.mkdir(parents=True)
        for index, name in enumerate(EXPECTED_DEMOS, start=1):
            _write_demo(log_dir, name, index)
        payload = refresh_latest_demo_evidence(log_dir)
        assert payload["passed"], payload["issues"]
        write_latest_demo_files(payload, log_dir)
        latest_json = log_dir / "latest.json"
        latest_md = log_dir / "latest.md"
        assert latest_json.exists()
        assert latest_md.exists()
        assert "Latest Passing Demo Evidence" in latest_md.read_text("utf-8")
        assert not validate_latest_demo_evidence(payload, log_dir=log_dir)
    print("demo_evidence_smoke: ok")


def _write_demo(log_dir: Path, name: str, index: int) -> None:
    base = log_dir / f"{name}-20260602T00000{index}Z"
    payload = {
        "name": name,
        "title": name.replace("_", " ").title(),
        "passed": True,
        "criteria": [f"{name} has explicit pass criteria"],
        "results": [
            {
                "command": f"{name}_smoke.py",
                "passed": True,
                "returncode": 0,
                "output": f"{name}: ok",
            }
        ],
        "artifacts": [],
    }
    base.with_suffix(".json").write_text(json.dumps(payload), encoding="utf-8")
    base.with_suffix(".md").write_text(f"# {name}\n\nStatus: PASS\n", encoding="utf-8")


if __name__ == "__main__":
    main()
