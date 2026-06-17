from __future__ import annotations


SAVE_MEMORY_TOOL_NAME = "save_maya_memory"
RECALL_MEMORY_TOOL_NAME = "recall_maya_memory"
FORGET_MEMORY_TOOL_NAME = "forget_maya_memory"


def save_memory_tool() -> dict:
    return {
        "type": "function",
        "name": SAVE_MEMORY_TOOL_NAME,
        "description": (
            "Use this when Zainal wants Maya to remember, save, note, or update a durable memory fact. "
            "Maya owns the semantic extraction: pass the exact fact to remember, not the whole filler transcript. "
            "This writes canonical memory directly and verifies the write. Call this before saying a memory was "
            "noted, saved, remembered, or updated; do not answer from conversation context alone."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "memory_text": {
                    "type": "string",
                    "description": "The durable memory fact Maya should save, in user-facing wording.",
                }
            },
            "required": ["memory_text"],
        },
    }


def recall_memory_tool() -> dict:
    return {
        "type": "function",
        "name": RECALL_MEMORY_TOOL_NAME,
        "description": (
            "Use this when Zainal asks Maya to recall a saved personal fact or preference from memory. "
            "Pass Maya's semantic query; Python retrieves only from memory and must not guess. Call this before "
            "answering a memory question; do not rely on the current voice conversation or short-term context."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The memory question or subject Maya wants to look up.",
                }
            },
            "required": ["query"],
        },
    }


def forget_memory_tool() -> dict:
    return {
        "type": "function",
        "name": FORGET_MEMORY_TOOL_NAME,
        "description": (
            "Use this when Zainal asks Maya to forget, remove, clear, or delete a saved memory fact. "
            "Pass the specific memory subject Maya understood. Call this before saying a memory was forgotten, "
            "removed, or cleared. Do not use revise_maya_work or start_maya_work for memory forgetting."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The specific memory subject or fact to forget.",
                }
            },
            "required": ["query"],
        },
    }
