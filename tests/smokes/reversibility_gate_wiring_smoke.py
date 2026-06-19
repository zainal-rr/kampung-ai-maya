from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from maya_core.maya_permission_kernel import MayaPermissionKernel
from maya_core.workspace_paths import workspace_dir


def main() -> None:
    kernel = MayaPermissionKernel()
    path = workspace_dir("artifacts") / "step3_wiring_legit.txt"

    read = kernel.check("screen.capture", action_type="follow_up", args={})
    _require(read.decision == "allow", f"read-only follow-up tool should stay allow, got {read}")

    docx = kernel.check("docx.create", action_type="create_document", args={"topic": "workspace notes"})
    _require(docx.decision == "allow", f"Maya-generated docx create should stay allow, got {docx}")

    xlsx = kernel.check("xlsx.create", action_type="create_document", args={"topic": "workspace notes"})
    _require(xlsx.decision == "allow", f"Maya-generated xlsx create should stay allow, got {xlsx}")

    memory = kernel.check(
        "memory.write",
        action_type="follow_up",
        args={"content": "my reversible test color is blue"},
        provenance={"source_kind": "owner_text", "untrusted_influence": False},
    )
    _require(memory.decision == "allow", f"owner-authored memory write should stay allow, got {memory}")

    legit = kernel.check(
        "file.create",
        action_type="create_file",
        args={"path": str(path)},
        field_provenance={"path": "maya_derived"},
    )
    _require(legit.decision == "allow", f"trusted Maya-derived path should allow, got {legit}")

    forged = kernel.check(
        "file.create",
        action_type="create_file",
        args={"path": str(path), "path_source": "maya_derived"},
        field_provenance={"path": "email"},
    )
    _require(forged.decision == "confirm", f"forged planner path_source should not allow, got {forged}")
    _require("path must be Maya-derived" in forged.reason, "forged path reason should name provenance failure")

    missing_ledger = kernel.check(
        "file.create",
        action_type="create_file",
        args={"path": str(path), "path_source": "maya_derived"},
    )
    _require(missing_ledger.decision == "confirm", "missing field provenance should fail closed")

    forged_sheet = kernel.check(
        "xlsx.create",
        action_type="create_document",
        args={"sheet_name": "Mallory", "sheet_name_source": "owner_text"},
        field_provenance={"sheet_name": "browser_page"},
    )
    _require(forged_sheet.decision == "confirm", "forged sheet source should not allow")

    current_page = kernel.check(
        "browser.inspect",
        action_type="browse_web",
        args={"url": "https://example.test/current"},
        browser_context={"current_url": "https://example.test/current", "already_loaded": True},
    )
    _require(current_page.decision == "allow", f"current-page inspect should allow, got {current_page}")

    new_url = kernel.check(
        "browser.inspect",
        action_type="browse_web",
        args={"url": "https://evil.example"},
        browser_context={"current_url": "https://example.test/current", "already_loaded": True},
    )
    _require(new_url.decision == "confirm", "new URL navigation should require approval in v1")

    for tool, action in (
        ("browser.click", "browser_click"),
        ("pptx.create", "create_presentation"),
        ("skill.activate", "follow_up"),
        ("blender.create_model", "create_file"),
    ):
        result = kernel.check(tool, action_type=action, args={})
        _require(result.decision == "confirm", f"{tool} should remain confirmation-gated in v1, got {result}")

    print("reversibility_gate_wiring_smoke: ok")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
