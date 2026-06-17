from __future__ import annotations


CONFIRM_ACTION_TOOL_NAME = "confirm_action"


def confirm_action_tool() -> dict:
    return {
        "type": "function",
        "name": CONFIRM_ACTION_TOOL_NAME,
        "description": (
            "Use this only to answer a pending safety confirmation. Maya interprets Zainal's yes/no, then calls "
            "this tool with the exact pending action id and fingerprint. Python never parses spoken confirmation text."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_id": {"type": "string", "description": "The pending action id Maya was given."},
                "approved": {
                    "type": "boolean",
                    "description": "True only when Zainal clearly approved this exact pending action.",
                },
                "action_fingerprint": {
                    "type": "string",
                    "description": "The action fingerprint Maya was given when asking for confirmation.",
                },
            },
            "required": ["action_id", "approved", "action_fingerprint"],
        },
    }
