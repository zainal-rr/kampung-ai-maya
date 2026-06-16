from __future__ import annotations

import logging

from curated_memory import add_curated_memory


def route_metadata(input_type: str, lane: str, reason: str, cost_recorded: bool) -> tuple[str, str, bool]:
    if input_type != "voice note":
        return lane, reason, cost_recorded
    return (
        f"xAI STT + {lane}",
        f"voice note transcribed, then {reason}",
        True,
    )


async def maybe_curate_memory(db_path: str, text: str, channel: str) -> None:
    lowered = text.lower()
    explicit_cues = ("remember that", "remember ", "i prefer", "my preference")
    durable_directives = ("do not ", "don't ", "must ")
    if not (
        any(cue in lowered for cue in explicit_cues)
        or lowered.startswith(durable_directives)
        or " maya should " in lowered
        or " kampung ai should " in lowered
    ):
        return
    try:
        await add_curated_memory(db_path, text, source=channel)
    except Exception:
        logging.exception("Curated memory write failed on channel %s", channel)
