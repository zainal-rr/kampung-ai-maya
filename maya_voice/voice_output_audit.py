from __future__ import annotations

import re


def audit_events_for_transcript(transcript: str, tool_calls: set[str]) -> list[tuple[str, str]]:
    events: list[tuple[str, str]] = []
    if _action_promise_without_tool(transcript, tool_calls):
        events.append(("voice_action_promise_without_tool", "voice_action_promise_without_tool"))
    if _memory_claim_without_memory_tool(transcript, tool_calls):
        events.append(("voice_memory_claim_without_memory_tool", "voice_memory_claim_without_memory_tool"))
    return events


def _action_promise_without_tool(transcript: str, tool_calls: set[str]) -> bool:
    if tool_calls:
        return False
    lowered = " ".join(str(transcript or "").lower().split())
    if not lowered:
        return False
    action_re = re.compile(
        r"\b(?:i(?:'ll| will| am going to|'m going to)|let me|one moment,?\s*i(?:'m| am)?)\s+"
        r"(?:create|make|open|check|inspect|update|revise|cancel|search|look|read|send|save)\b"
    )
    return bool(action_re.search(lowered))


def _memory_claim_without_memory_tool(transcript: str, tool_calls: set[str]) -> bool:
    memory_tools = {"save_maya_memory", "recall_maya_memory", "forget_maya_memory"}
    if memory_tools.intersection(tool_calls):
        return False
    lowered = " ".join(str(transcript or "").lower().split())
    if not lowered:
        return False
    claim_re = re.compile(
        r"\b(?:i(?:'ve| have)?|i'll|i will)?\s*"
        r"(?:noted|saved|remembered|updated|forgotten|removed|cleared|recalled)\b"
    )
    memory_re = re.compile(r"\b(?:memory|remember|preference|noted|saved|forgotten|project notebook|preferred)\b")
    return bool(claim_re.search(lowered) and memory_re.search(lowered))
