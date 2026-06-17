from __future__ import annotations

from maya_core.assistant_command_helpers import filter_user_visible_memory, format_memory_reply
from maya_core.permission_policy import contains_sensitive_info, hard_no_private_exposure_text
from maya_memory.canonical_memory import search_canonical_direct_fact, upsert_canonical_memory
from maya_memory.memory_control import forget_memory
from maya_memory.memory_perspective import normalize_user_perspective_memory
from maya_memory.memory_service import MemoryService
from maya_voice.tool_results import tool_result_for_maya


async def save_voice_memory(db_path: str, memory_text: str) -> str:
    fact = normalize_user_perspective_memory(" ".join(str(memory_text).split()).strip())
    if not fact:
        return tool_result_for_maya("", "empty_request", status="needs_clarification")
    if contains_sensitive_info(fact):
        return tool_result_for_maya(fact, hard_no_private_exposure_text(), status="hard_blocked")
    memory_id = await upsert_canonical_memory(
        db_path,
        raw_text=memory_text,
        content=fact,
        kind="preference",
        scope="global",
        source_channel="imac_voice",
        confidence="high",
    )
    recalled = await search_canonical_direct_fact(db_path, fact, limit=3)
    if recalled is None or not recalled:
        result = "memory_write_unverified: I wrote the memory, but direct recall did not verify it."
        return tool_result_for_maya(fact, result, status="failed")
    result = (
        "memory_saved\n"
        f"memory_id: {memory_id}\n"
        f"saved_fact: {fact}\n"
        "verified: canonical direct recall found the saved fact."
    )
    return tool_result_for_maya(fact, result, status="completed")


async def recall_voice_memory(db_path: str, query: str) -> str:
    cleaned = " ".join(str(query).split()).strip()
    snippets = filter_user_visible_memory(await MemoryService(db_path).search_direct_fact(cleaned, limit=3))
    if not snippets:
        result = "memory_not_found: I do not have that saved in canonical memory."
        return tool_result_for_maya(cleaned, result, status="completed")
    return tool_result_for_maya(cleaned, format_memory_reply(cleaned, snippets, False), status="completed")


async def forget_voice_memory(db_path: str, query: str) -> str:
    cleaned = " ".join(str(query).split()).strip()
    result = await forget_memory(db_path, cleaned)
    status = "completed" if "Removed" in result or "could not find" in result else "failed"
    return tool_result_for_maya(cleaned, result, status=status)
