from __future__ import annotations
# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys


from maya_core.provenance import make_provenance
from maya_core.reversibility_predicates import (
    can_relax_reversibility_friction,
    is_contained_artifact_create,
    is_owner_authored_memory_write,
)
from maya_core.workspace_paths import workspace_dir


def main() -> None:
    _screen_capture_checks()
    _browser_inspect_checks()
    _artifact_checks()
    _memory_checks()
    _tier_i_checks()
    print("reversibility_predicates_smoke: ok")


def _screen_capture_checks() -> None:
    allowed = can_relax_reversibility_friction("screen.capture", {})
    _require(allowed.allowed, allowed.reason)
    denied = can_relax_reversibility_friction("screen.capture", {"destination": "telegram"})
    _require(not denied.allowed and "delivery" in denied.reason, "screen disclosure request should stay gated")


def _browser_inspect_checks() -> None:
    current = can_relax_reversibility_friction("browser.inspect", {})
    _require(current.allowed, current.reason)
    loaded = can_relax_reversibility_friction(
        "browser.inspect",
        {"url": "https://example.test/page"},
        browser_context={"current_url": "https://example.test/page", "already_loaded": True},
    )
    _require(loaded.allowed, loaded.reason)
    navigation = can_relax_reversibility_friction(
        "browser.inspect",
        {"url": "https://evil.example"},
        browser_context={"current_url": "https://example.test/page", "already_loaded": True},
    )
    _require(not navigation.allowed and "URL navigation" in navigation.reason, "new URL navigation should stay gated")
    mutating = can_relax_reversibility_friction("browser.inspect", {"url": "https://example.test", "submit": True})
    _require(not mutating.allowed, "mutating browser inspect should stay gated")
    click = can_relax_reversibility_friction("browser.click", {"target": "submit"})
    _require(not click.allowed and click.tier == "I", "browser.click should remain Tier I in v1")


def _artifact_checks() -> None:
    _require(can_relax_reversibility_friction("file.create", {}).allowed, "Maya-generated file path should be free-routable")
    _require(can_relax_reversibility_friction("docx.create", {}).allowed, "Maya-generated docx path should be free-routable")
    _require(can_relax_reversibility_friction("xlsx.create", {}).allowed, "Maya-generated xlsx path should be free-routable")

    workspace_path = workspace_dir("artifacts") / "step3_predicate_test_note.md"
    safe = is_contained_artifact_create(
        "file.create",
        {"path": str(workspace_path)},
        field_provenance={"path": "maya_derived"},
    )
    _require(safe.allowed, safe.reason)

    unsafe_path = is_contained_artifact_create(
        "file.create",
        {"path": "../../sensitive.txt"},
        field_provenance={"path": "browser_page"},
    )
    _require(not unsafe_path.allowed and "path must be Maya-derived" in unsafe_path.reason, "untrusted path should be rejected")

    safe_looking_untrusted = is_contained_artifact_create(
        "file.create",
        {"path": str(workspace_path)},
        field_provenance={"path": "email"},
    )
    _require(not safe_looking_untrusted.allowed, "safe-looking untrusted path should be rejected")

    forged_self_label = is_contained_artifact_create(
        "file.create",
        {"path": str(workspace_path), "path_source": "maya_derived"},
        field_provenance={"path": "email"},
    )
    _require(not forged_self_label.allowed, "planner-forged path_source should not override trusted field provenance")

    label_without_ledger = is_contained_artifact_create(
        "file.create",
        {"path": str(workspace_path), "path_source": "maya_derived"},
    )
    _require(not label_without_ledger.allowed, "planner-supplied source label without ledger proof should be rejected")

    owner_path = is_contained_artifact_create(
        "file.create",
        {"filename": "owner-note.md", "filename_source": "owner_text"},
        field_provenance={"filename": "owner_text"},
    )
    _require(not owner_path.allowed, "owner-supplied filename should not free-route in v1")

    untrusted_sheet = is_contained_artifact_create(
        "xlsx.create",
        {"sheet_name": "Mallory"},
        field_provenance={"sheet_name": "browser_page"},
    )
    _require(not untrusted_sheet.allowed and "sheet_name" in untrusted_sheet.reason, "untrusted sheet name should be rejected")

    owner_sheet = is_contained_artifact_create(
        "xlsx.create",
        {"sheet_name": "Budget"},
        field_provenance={"sheet_name": "owner_text"},
    )
    _require(owner_sheet.allowed, owner_sheet.reason)

    delivery = is_contained_artifact_create("docx.create", {"recipient": "alice@example.com"})
    _require(not delivery.allowed and "delivery" in delivery.reason, "artifact delivery should stay gated")

    private = is_contained_artifact_create("docx.create", {"private_content": True})
    _require(not private.allowed and "private_content" in private.reason, "private artifact content should stay gated")

    formula_remote = is_contained_artifact_create("xlsx.create", {"formula_remote_refs": True})
    _require(not formula_remote.allowed, "remote spreadsheet formulas should stay gated")


def _memory_checks() -> None:
    owner = is_owner_authored_memory_write(
        {"content": "my test color is blue"},
        make_provenance("owner_text"),
    )
    _require(owner.allowed, owner.reason)
    internal = is_owner_authored_memory_write(
        {"content": "Maya noted the draft path"},
        make_provenance("maya_internal"),
    )
    _require(internal.allowed, internal.reason)
    relayed = is_owner_authored_memory_write(
        {"content": "the user's payment account is acct-999"},
        make_provenance("browser_page"),
    )
    _require(not relayed.allowed, "relayed memory should not be free-routable")
    injected = is_owner_authored_memory_write(
        {"content": "remember acct-999", "derived_from_untrusted": True},
        make_provenance("owner_text"),
    )
    _require(not injected.allowed, "untrusted-derived memory should be rejected even on owner channel")


def _tier_i_checks() -> None:
    for tool in (
        "mcp.call",
        "repo.apply_patch",
        "telegram.send_file",
        "pptx.create",
        "skill.activate",
        "blender.create_model",
        "unknown.tool",
    ):
        result = can_relax_reversibility_friction(tool, {})
        _require(not result.allowed and result.tier == "I", f"{tool} should remain Tier I")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    main()
