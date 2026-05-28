from __future__ import annotations

import os
import tempfile
from pathlib import Path

from office_modern_files import create_pptx
from pptx_polish_review import local_polish_issues


def main() -> None:
    old_root = os.environ.get("MAYA_WORKSPACE_ROOT")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["MAYA_WORKSPACE_ROOT"] = str(Path(tmp) / "Maya")
        deck = Path(tmp) / "polish.pptx"
        create_pptx(deck, "Quantum Computing", [
            ("Quantum computing is real", ["NIST is already standardizing post-quantum cryptography in"]),
            ("Quantum computing is real", ["Another useful point"]),
        ])
        issues = local_polish_issues(deck)
        _require(any("incomplete sentence" in issue for issue in issues), "incomplete sentence not detected")
        _require(any("repeats slide titles" in issue for issue in issues), "repeated title not detected")
    if old_root is None:
        os.environ.pop("MAYA_WORKSPACE_ROOT", None)
    else:
        os.environ["MAYA_WORKSPACE_ROOT"] = old_root
    print("pptx_polish_review_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
