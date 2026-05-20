from __future__ import annotations

import os

from permission_policy import action_permission


class AutonomyPolicy:
    """
    Keeps Maya bounded. Safe actions can be automated, but sensitive actions
    should pause unless the runtime is explicitly trusted to go further.
    """

    def __init__(self, default_mode: str | None = None):
        self.default_mode = (default_mode or os.getenv("KAMPUNG_AUTONOMY_MODE", "auto_safe")).lower()

    def can_auto_execute(self, action_type: str, task_mode: str | None = None) -> bool:
        mode = (task_mode or self.default_mode).lower()
        if mode == "observe":
            return False
        permission = action_permission(action_type)
        if permission == "allow":
            return mode in {"auto_safe", "ask_sensitive", "full"}
        if permission == "confirm":
            return mode in {"approved", "full"}
        return False

    def blocked_status(self, action_type: str) -> str:
        if action_permission(action_type) == "deny":
            return "denied"
        if action_permission(action_type) == "confirm":
            return "awaiting_confirmation"
        return "pending"

    def blocked_reason(self, action_type: str) -> str:
        permission = action_permission(action_type)
        if permission == "deny":
            return f"{action_type} is blocked by the private exposure policy."
        if permission == "confirm":
            return f"{action_type} needs explicit confirmation."
        return f"{action_type} is not enabled for autonomous execution."
