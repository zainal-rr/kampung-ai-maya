from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from maya_core.maya_tool_registry import MayaToolRegistry, default_maya_tool_registry
from maya_core.permission_policy import hard_no_private_exposure_text
from maya_core.tool_sandbox_policy import sandbox_decision, stricter_decision
from untrusted_input_boundary import untrusted_action_decision


@dataclass(frozen=True)
class PermissionDecision:
    decision: str
    tool_name: str
    action_type: str
    reason: str
    approval_required: bool = False
    replay_safe: bool = False
    side_effect_level: str = "unknown"
    cost_risk: str = "unknown"
    risk_class: str = "unknown"


def _args_text(args: Mapping[str, Any] | None) -> str:
    """Extract human-readable text from tool args for the permission policy.

    The policy's markers and exposure starters are written for natural language,
    not JSON syntax, so feed it the string values rather than a serialized blob.
    """
    parts: list[str] = []
    for value in dict(args or {}).values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (list, tuple)):
            parts.extend(str(item) for item in value if isinstance(item, str))
    return " ".join(parts)


class MayaPermissionKernel:
    def __init__(self, registry: MayaToolRegistry | None = None):
        self.registry = registry or default_maya_tool_registry()

    def check(
        self,
        tool_name: str,
        *,
        action_type: str = "",
        args: Mapping[str, Any] | None = None,
        untrusted_influence: bool = False,
        injection_detected: bool = False,
    ) -> PermissionDecision:
        spec = self.registry.get(tool_name)
        payload = _args_text(args)
        if not spec:
            base = PermissionDecision(
                "confirm",
                tool_name,
                action_type or "unknown",
                "unknown tool requires approval",
                approval_required=True,
                replay_safe=False,
                side_effect_level="unknown",
                risk_class="unknown",
            )
            return self._apply_untrusted_boundary(base, untrusted_influence, injection_detected)
        effective_action = action_type or spec.permission_scope
        decision = spec.permission(payload)
        sandbox = sandbox_decision(
            tool_name,
            action_type=effective_action,
            side_effect_level=spec.side_effect_level,
        )
        decision = stricter_decision(decision, sandbox.required_decision)
        if decision == "deny":
            reason = hard_no_private_exposure_text()
        elif decision == "confirm":
            reason = sandbox.reason if sandbox.required_decision == "confirm" else "approval required before tool execution"
        else:
            reason = "allowed by tool registry and permission policy"
        base = PermissionDecision(
            decision,
            tool_name,
            effective_action,
            reason,
            approval_required=decision == "confirm",
            replay_safe=spec.replay_safe,
            side_effect_level=spec.side_effect_level,
            cost_risk=spec.cost_risk,
            risk_class=sandbox.risk_class,
        )
        return self._apply_untrusted_boundary(base, untrusted_influence, injection_detected)

    @staticmethod
    def _apply_untrusted_boundary(
        base: PermissionDecision,
        untrusted_influence: bool,
        injection_detected: bool,
    ) -> PermissionDecision:
        """W7 untrusted-input boundary, applied after the base decision.

        Default (no untrusted influence) → returns base unchanged, so existing
        behavior is byte-identical. When the turn read untrusted content, an
        external/scope-widening/unknown tool is gated (confirm) or, on detected
        injection, denied. Never loosens the base decision."""
        if not untrusted_influence and not injection_detected:
            return base
        boundary = untrusted_action_decision(
            base.tool_name,
            untrusted_influence=untrusted_influence,
            injection_detected=injection_detected,
            base_decision=base.decision,
            side_effect_level=base.side_effect_level,
        )
        if boundary.decision == base.decision:
            return base
        from dataclasses import replace

        return replace(
            base,
            decision=boundary.decision,
            reason=boundary.reason,
            approval_required=boundary.decision == "confirm",
        )
