from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from maya_tool_registry import MayaToolRegistry, default_maya_tool_registry
from permission_policy import hard_no_private_exposure_text


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


class MayaPermissionKernel:
    def __init__(self, registry: MayaToolRegistry | None = None):
        self.registry = registry or default_maya_tool_registry()

    def check(
        self,
        tool_name: str,
        *,
        action_type: str = "",
        args: Mapping[str, Any] | None = None,
    ) -> PermissionDecision:
        spec = self.registry.get(tool_name)
        payload = json.dumps(dict(args or {}), sort_keys=True, default=str)
        if not spec:
            return PermissionDecision(
                "confirm",
                tool_name,
                action_type or "unknown",
                "unknown tool requires approval",
                approval_required=True,
                replay_safe=False,
            )
        effective_action = action_type or spec.permission_scope
        decision = spec.permission(payload)
        if decision == "deny":
            reason = hard_no_private_exposure_text()
        elif decision == "confirm":
            reason = "approval required before tool execution"
        else:
            reason = "allowed by tool registry and permission policy"
        return PermissionDecision(
            decision,
            tool_name,
            effective_action,
            reason,
            approval_required=decision == "confirm",
            replay_safe=spec.replay_safe,
            side_effect_level=spec.side_effect_level,
            cost_risk=spec.cost_risk,
        )
