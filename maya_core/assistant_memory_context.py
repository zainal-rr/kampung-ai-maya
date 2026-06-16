from __future__ import annotations

from context_window import assemble_recent_context, resolve_route
from curated_memory import curated_memory_prompt
from project_store import build_project_context
from quantum_advisory import quantum_context_hint
from session_compactor import build_session_context
from telegram_context_policy import should_use_full_context


async def build_assistant_memory_context(
    *,
    db_path: str,
    memory,
    text: str,
    channel: str,
    input_type: str,
    complex_route: bool,
    sight_route: bool,
) -> str:
    if not should_use_full_context(
        text,
        channel=channel,
        input_type=input_type,
        complex_route=complex_route,
        sight_route=sight_route,
    ):
        return ""
    # Context-window chokepoint (docs/context_window_design_2026-06-12.md):
    # this function is Maya's single context funnel, so the raw window joins
    # it here rather than beside it. Block order keeps stable tiers first and
    # the volatile raw window LAST (cache-friendly + recency never outranks
    # the authoritative tiers). Returns "" while MAYA_CONTEXT_WINDOW=0.
    window = await assemble_recent_context(
        db_path,
        channel=channel,
        route=resolve_route(channel, complex_route=complex_route),
    )
    blocks = (
        await build_project_context(db_path, text),
        await curated_memory_prompt(db_path),
        await build_session_context(db_path, text),
        await quantum_context_hint(db_path, text),
        await memory.build_prompt_context(text),
        window.text,
    )
    return "\n\n".join(block for block in blocks if block)
