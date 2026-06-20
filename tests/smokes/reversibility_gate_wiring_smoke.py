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
from harness_helpers.graph_runner import _trusted_agentic_artifact_args


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

    owner_path_state = {
        "goal": "Create a local file notes/c0-field-note.txt with three bullets.",
        "user_text": "Create a local file notes/c0-field-note.txt with three bullets.",
        "last_user_instruction": "Create a local file notes/c0-field-note.txt with three bullets.",
    }
    normalized, provenance = _trusted_agentic_artifact_args(
        owner_path_state,
        "file.create",
        {"path": "notes/c0-field-note.txt", "content": "draft bullets"},
    )
    _require(provenance == {"path": "maya_derived"}, f"owner path provenance not derived: {provenance}")
    owner_path = kernel.check("file.create", action_type="create_file", args=normalized, field_provenance=provenance)
    _require(owner_path.decision == "allow", f"owner visible path should free-route after harness derivation: {owner_path}")

    research_state = {
        **owner_path_state,
        "untrusted_influence": True,
        "last_observation": {"source": "browser_page", "text_summary": "untrusted content for the draft body"},
    }
    research_args, research_provenance = _trusted_agentic_artifact_args(
        research_state,
        "file.create",
        {"path": "notes/c0-field-note.txt", "content": "draft from browser evidence"},
    )
    research_create = kernel.check(
        "file.create",
        action_type="create_file",
        args=research_args,
        field_provenance=research_provenance,
        untrusted_influence=True,
    )
    _require(research_create.decision == "allow", f"untrusted content must not taint Maya-derived path: {research_create}")

    raw_path_args, raw_path_provenance = _trusted_agentic_artifact_args(
        {"goal": "Create a local note.", "user_text": "Create a local note."},
        "file.create",
        {"path": "notes/from-email.txt", "path_source": "maya_derived", "content": "draft"},
    )
    raw_path = kernel.check(
        "file.create",
        action_type="create_file",
        args=raw_path_args,
        field_provenance=raw_path_provenance,
    )
    _require(raw_path.decision == "confirm", f"planner raw/forged path should still require approval: {raw_path}")

    delivery_args, delivery_provenance = _trusted_agentic_artifact_args(
        owner_path_state,
        "file.create",
        {"path": "notes/c0-field-note.txt", "content": "draft bullets", "recipient": "alice@example.com"},
    )
    delivery = kernel.check(
        "file.create",
        action_type="create_file",
        args=delivery_args,
        field_provenance=delivery_provenance,
    )
    _require(delivery.decision == "confirm", "delivery flag must keep local create gated")

    outside_args, outside_provenance = _trusted_agentic_artifact_args(
        {
            "goal": "Create a local file /tmp/c0-outside.txt with a note.",
            "user_text": "Create a local file /tmp/c0-outside.txt with a note.",
        },
        "file.create",
        {"path": "/tmp/c0-outside.txt", "content": "note"},
    )
    outside = kernel.check("file.create", action_type="create_file", args=outside_args, field_provenance=outside_provenance)
    _require(outside.decision == "confirm", "outside-workspace path must require approval")

    existing_path = workspace_dir("artifacts", create=True) / "step3-existing-target.txt"
    existing_path.write_text("already here", encoding="utf-8")
    existing_args, existing_provenance = _trusted_agentic_artifact_args(
        {
            "goal": f"Create a local file {existing_path} with a note.",
            "user_text": f"Create a local file {existing_path} with a note.",
        },
        "file.create",
        {"path": str(existing_path), "content": "note"},
    )
    existing = kernel.check("file.create", action_type="create_file", args=existing_args, field_provenance=existing_provenance)
    _require(existing.decision == "confirm", "existing artifact target must require approval")
    existing_path.unlink(missing_ok=True)

    forged_sheet = kernel.check(
        "xlsx.create",
        action_type="create_document",
        args={"sheet_name": "Mallory", "sheet_name_source": "owner_text"},
        field_provenance={"sheet_name": "browser_page"},
    )
    _require(forged_sheet.decision == "confirm", "forged sheet source should not allow")

    sheet_args, sheet_provenance = _trusted_agentic_artifact_args(
        {"goal": "Create a spreadsheet named C0 Scores.", "user_text": "Create a spreadsheet named C0 Scores."},
        "xlsx.create",
        {"sheet_name": "C0 Scores"},
    )
    sheet = kernel.check("xlsx.create", action_type="create_document", args=sheet_args, field_provenance=sheet_provenance)
    _require(sheet.decision == "allow", f"owner visible sheet name should allow: {sheet}")

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
