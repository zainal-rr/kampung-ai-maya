"""Closed-world router clearance conformance smoke.

This is a measurement ratchet, not a policy engine. It fails when a routed
handler/callsite exists without a clearance row, or when an active surface lacks
gate placement and a conformance id.
"""

from __future__ import annotations

# W4_TEST_ROOT_BOOTSTRAP
import sys as _w4_sys
from pathlib import Path as _w4_Path
_w4_root = _w4_Path(__file__).resolve().parents[2]
if str(_w4_root) not in _w4_sys.path:
    _w4_sys.path.insert(0, str(_w4_root))
del _w4_Path, _w4_root, _w4_sys

from dataclasses import replace
from pathlib import Path

from maya_core.router_clearance_registry import (
    ACTIVE_CLASSIFICATIONS,
    RouteSurface,
    callsite_marker_issues,
    fix_register,
    route_surfaces,
    source_inventory_issues,
    validate_registry,
)


ROOT = Path(__file__).resolve().parents[2]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _by_id() -> dict[str, RouteSurface]:
    return {surface.surface_id: surface for surface in route_surfaces()}


def _registry_shape_checks() -> None:
    issues = validate_registry()
    _require(not issues, "registry issues:\n" + "\n".join(issues))
    surfaces = _by_id()
    required = {
        "assistant.handle_text",
        "assistant.learning",
        "assistant.harness",
        "assistant.commands",
        "assistant.vision",
        "assistant.screen",
        "assistant.router",
        "assistant.direct_command",
        "assistant.context_command",
        "assistant_routes._route_inner",
        "routes.commands_inner",
        "routes.commands_segment",
        "routes.learning_segment",
        "routes.policy_inner",
        "routes.policy_segment",
        "routes.fast_telegram_sight",
        "routes.fast_telegram_default",
        "routes.fast_telegram_normal",
        "routes.fast_telegram_segment",
        "routes.fast_imac",
        "routes.complex_plan_explicit",
        "routes.complex_plan_imac",
        "routes.complex_explicit",
        "routes.complex_imac",
        "routes.artisan",
        "routes.steward",
        "routes.source_imac",
        "routes.source_telegram",
        "routes.pulse",
        "assistant_commands._handle_memory_forget",
        "assistant_commands._handle_context_window",
        "assistant_commands._handle_preference_listing",
        "telegram_commands.command_to_text",
        "context_command.handle_context_command",
        "learning.handle",
        "harness._confirmation",
        "document.handle",
        "document_html._create_html",
        "document_word._edit_latest_document",
        "document_office._create_powerpoint",
        "document_excel._create_excel",
        "imac_workflows._browser_click",
        "human_browser.handle",
        "human_browser.handle_confirmation",
        "visual_workflow.handle",
        "screen.handle",
        "vision.handle",
        "model_lanes._prompt",
    }
    missing = sorted(required - set(surfaces))
    _require(not missing, f"missing required surfaces: {missing}")
    for key in required:
        surface = surfaces[key]
        if surface.classification in ACTIVE_CLASSIFICATIONS:
            _require(surface.gate_placement != "not_applicable", f"{key} missing gate placement")
            _require(surface.conformance_test_id, f"{key} missing conformance id")
    _require(surfaces["assistant.learning"].gate_placement == "gate_at_callsite", "peer call must be callsite-marked")
    _require(surfaces["learning.handle"].gate_placement == "gate_internal", "learning handler gate should be internal")
    _dual_path_checks(surfaces)
    _require(surfaces["assistant_commands._handle_context_window"].classification == "disclosure", "context row must be disclosure")
    _require(surfaces["assistant_commands._handle_memory_forget"].classification == "effect", "forget row must be effect")


def _dual_path_checks(surfaces: dict[str, RouteSurface]) -> None:
    """Shared peers must have callsite rows plus an internal handler row.

    This is the exact failure mode that used to hide above AssistantCommandRouter:
    a handler can be reachable through two orchestrators. If its gate is internal,
    both paths inherit it; if the gate is at the callsite, every callsite must be
    represented separately.
    """
    pairs = {
        "learning": ("assistant.learning", "routes.learning_segment", "learning.handle"),
        "commands": ("assistant.commands", "routes.commands_inner", "routes.commands_segment", "assistant_commands.handle"),
        "policy": ("routes.policy_inner", "routes.policy_segment", "policy.reply"),
    }
    for label, ids in pairs.items():
        missing = [surface_id for surface_id in ids if surface_id not in surfaces]
        _require(not missing, f"{label} dual-path coverage missing {missing}")
    _require(surfaces["learning.handle"].gate_placement == "gate_internal", "learning dual path must rely on internal gate")
    _require(surfaces["assistant_commands.handle"].gate_placement == "gate_internal", "commands dual path must rely on internal gate")
    _require(surfaces["policy.reply"].gate_placement == "gate_internal", "policy dual path must rely on internal gate")
    for surface_id in (
        "assistant.learning",
        "routes.learning_segment",
        "assistant.commands",
        "routes.commands_inner",
        "routes.commands_segment",
        "routes.policy_inner",
        "routes.policy_segment",
    ):
        _require(surfaces[surface_id].gate_placement == "gate_at_callsite", f"{surface_id} must be callsite-marked")


def _source_ratchet_checks() -> None:
    issues = source_inventory_issues(ROOT)
    _require(not issues, "source inventory issues:\n" + "\n".join(issues))
    marker_issues = callsite_marker_issues(ROOT)
    _require(not marker_issues, "callsite marker issues:\n" + "\n".join(marker_issues))


def _canary_checks() -> None:
    surfaces = route_surfaces()
    canary = replace(
        surfaces[0],
        surface_id="ungated.canary",
        classification="both",
        required_gate="none",
        gate_placement="ungated_canary",
    )
    issues = validate_registry((canary,))
    _require(issues, "ungated active canary must fail registry validation")


def _seven_fix_register_checks() -> None:
    fixes = {entry.fix_id: entry for entry in fix_register()}
    expected = {
        "relayed_content_owner",
        "mcp_call_action_type",
        "skill_scaffold_private",
        "rewrite_swallow",
        "document_edit_route",
        "approval_boundary",
        "recovered_masks_work",
    }
    _require(set(fixes) == expected, f"seven-fix register mismatch: {sorted(fixes)}")
    for entry in fixes.values():
        _require(entry.verification in {"regression-pinnable", "manual-or-regression"}, f"bad verification: {entry}")
        _require(entry.evidence, f"missing evidence for {entry.fix_id}")


def main() -> None:
    _registry_shape_checks()
    _source_ratchet_checks()
    _canary_checks()
    _seven_fix_register_checks()
    print("router_clearance_conformance_smoke: ok")


if __name__ == "__main__":
    main()
