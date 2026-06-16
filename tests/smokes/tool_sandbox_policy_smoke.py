from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


import sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from maya_core.maya_permission_kernel import MayaPermissionKernel
from permission_policy import action_permission
from tool_sandbox_policy import (
    BROWSER_AUTOMATION,
    EXTERNAL,
    FILE_WRITE,
    READ_ONLY,
    REPO_WRITE,
    classify_tool_risk,
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    kernel = MayaPermissionKernel()
    screen = kernel.check("screen.capture")
    _require(screen.decision == "allow", f"screen read should be allowed, got {screen}")
    _require(screen.risk_class == READ_ONLY, f"screen risk wrong: {screen.risk_class}")

    browser = kernel.check("browser.click", args={"target": "Search"})
    _require(browser.decision == "allow", f"safe browser click should be allowed, got {browser}")
    _require(browser.risk_class == BROWSER_AUTOMATION, f"browser risk wrong: {browser.risk_class}")

    document = kernel.check("docx.create", args={"topic": "school robotics workshop"})
    _require(document.decision == "allow", f"local doc creation should be allowed, got {document}")
    _require(document.risk_class == FILE_WRITE, f"document risk wrong: {document.risk_class}")

    repo = kernel.check("repo.apply_patch", args={"repo_path": "."})
    _require(repo.decision == "confirm", f"repo write should require confirmation, got {repo}")
    _require(repo.risk_class == REPO_WRITE, f"repo risk wrong: {repo.risk_class}")

    external = kernel.check("telegram.send_file", args={"path": "/tmp/report.docx"})
    _require(external.decision == "confirm", f"external send should require confirmation, got {external}")
    _require(external.risk_class == EXTERNAL, f"external risk wrong: {external.risk_class}")

    injected = kernel.check(
        "telegram.send_file",
        args={"path": "/tmp/report.docx"},
        untrusted_influence=True,
        injection_detected=True,
    )
    _require(injected.decision == "deny", f"injected external send should be denied, got {injected}")

    unknown = kernel.check("unknown.tool")
    _require(unknown.decision == "confirm", f"unknown tool should require confirmation, got {unknown}")
    _require(
        classify_tool_risk("file.create", action_type="delete_file", side_effect_level="write") == "destructive",
        "delete_file should classify as destructive",
    )
    _require(action_permission("delete_file") == "confirm", "delete_file baseline policy changed")

    print("tool_sandbox_policy_smoke: ok")


if __name__ == "__main__":
    main()
