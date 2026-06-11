from __future__ import annotations

"""Tool blast-radius policy for Maya.

This is the W5 sandbox contract used by the permission kernel. It does not
replace the existing tool registry or W7 untrusted-input boundary; it gives the
kernel one place to classify risk and fail closed for high-blast-radius actions.
"""

from dataclasses import dataclass


READ_ONLY = "read_only"
BROWSER_AUTOMATION = "browser_automation"
FILE_WRITE = "file_write"
REPO_WRITE = "repo_write"
DESTRUCTIVE = "destructive"
EXTERNAL = "external"
UNKNOWN = "unknown"

_DESTRUCTIVE_ACTIONS = {
    "delete_file",
    "delete_resource",
    "deploy_repair",
    "restart_service",
}

_EXTERNAL_ACTIONS = {
    "send_message",
    "share_file",
    "upload_file",
    "submit_form",
    "book_travel",
    "purchase_item",
    "make_payment",
    "telegram_send",
}

_BROWSER_ACTIONS = {
    "browse_web",
    "browser_click",
    "travel_search",
    "sensitive_browser_click",
}


@dataclass(frozen=True)
class ToolSandboxDecision:
    risk_class: str
    required_decision: str
    reason: str

    @property
    def approval_required(self) -> bool:
        return self.required_decision == "confirm"


def classify_tool_risk(
    tool_name: str,
    *,
    action_type: str,
    side_effect_level: str,
) -> str:
    action = str(action_type or "").strip()
    level = str(side_effect_level or "").strip().lower()
    name = str(tool_name or "").strip()
    if action in _DESTRUCTIVE_ACTIONS:
        return DESTRUCTIVE
    if level == "external" or action in _EXTERNAL_ACTIONS:
        return EXTERNAL
    if level == "repo_write" or action == "apply_code_patch" or name.startswith("repo."):
        return REPO_WRITE
    if action in _BROWSER_ACTIONS or name.startswith("browser."):
        return BROWSER_AUTOMATION
    if level == "write":
        return FILE_WRITE
    if level == "read":
        return READ_ONLY
    return UNKNOWN


def sandbox_decision(
    tool_name: str,
    *,
    action_type: str,
    side_effect_level: str,
) -> ToolSandboxDecision:
    risk = classify_tool_risk(
        tool_name,
        action_type=action_type,
        side_effect_level=side_effect_level,
    )
    if risk == READ_ONLY:
        return ToolSandboxDecision(risk, "allow", "read-only local inspection is allowed")
    if risk == BROWSER_AUTOMATION:
        return ToolSandboxDecision(risk, "allow", "browser automation is allowed inside the Maya browser boundary")
    if risk == FILE_WRITE:
        return ToolSandboxDecision(risk, "allow", "local file creation/editing is allowed inside Maya workspaces")
    if risk in {REPO_WRITE, DESTRUCTIVE, EXTERNAL, UNKNOWN}:
        return ToolSandboxDecision(risk, "confirm", f"{risk.replace('_', ' ')} action requires explicit approval")
    return ToolSandboxDecision(UNKNOWN, "confirm", "unknown tool risk requires explicit approval")


def stricter_decision(current: str, required: str) -> str:
    order = {"allow": 0, "confirm": 1, "deny": 2}
    return current if order.get(current, 1) >= order.get(required, 1) else required
