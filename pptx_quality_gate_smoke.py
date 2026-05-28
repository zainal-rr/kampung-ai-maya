from __future__ import annotations

import os
import tempfile
from pathlib import Path

from office_modern_files import create_pptx
from pptx_quality_gate import ensure_pptx_quality, inspect_pptx_quality


def main() -> None:
    old_root = os.environ.get("MAYA_WORKSPACE_ROOT")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        bad = Path(tmp) / "bad.pptx"
        create_pptx(bad, "Placeholder Deck", [("Intro", ["Meta Ray Ban Display visual anchor"])])
        before = inspect_pptx_quality(bad)
        _require(not before.passed, "placeholder deck should fail QA")
        good = Path(tmp) / "good.pptx"
        create_pptx(good, "Router Setup", [
            ("Router Setup", ["WAN planning", "LAN addressing", "Firewall baseline"]),
            ("Implementation", ["Connect uplink", "Create VLANs", "Test failover"]),
        ])
        after = ensure_pptx_quality(good, max_revisions=1)
        _require(after.passed, "normal generated deck should pass QA")
        _require(after.images and all(path.exists() for path in after.images), "QA did not render slides")
    if old_root is None:
        os.environ.pop("MAYA_WORKSPACE_ROOT", None)
    else:
        os.environ["MAYA_WORKSPACE_ROOT"] = old_root
    print("pptx_quality_gate_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
